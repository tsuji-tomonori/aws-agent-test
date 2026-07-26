from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

REQUIRED_KEYS = {
    "schema_version",
    "case_id",
    "status",
    "region",
    "currency",
    "price_effective_at",
    "monthly_total_usd",
    "service_estimates",
    "assumptions",
    "excluded_costs",
    "missing_inputs",
    "confidence",
    "summary",
}


def _contains(condition: str, token: str) -> bool:
    return token in condition.split("+")


def _copy_skill(repo_root: Path, workspace: Path) -> None:
    source = Path(
        os.environ.get(
            "AWS_AGENT_SKILL_SOURCE",
            str(repo_root / "benchmarks/aws-agent-ablation/skills/deploy"),
        )
    ).resolve()
    if not (source / "SKILL.md").is_file():
        raise ValueError(f"AWS deploy skill source is missing SKILL.md: {source}")
    target = workspace / ".opencode/skills/deploy"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _write_config(workspace: Path, condition: str, model: str, repo_root: Path) -> Path:
    mcp: dict[str, Any] = {}
    if _contains(condition, "knowledge"):
        mcp["aws_knowledge"] = {
            "type": "remote",
            "url": "https://knowledge-mcp.global.api.aws",
            "enabled": True,
            "oauth": False,
            "timeout": 30000,
        }
    if _contains(condition, "pricing"):
        mcp["frozen_pricing"] = {
            "type": "local",
            "command": [
                sys.executable,
                str(repo_root / "benchmarks/aws-agent-ablation/frozen_pricing_mcp.py"),
            ],
            "enabled": True,
            "timeout": 10000,
        }

    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "ollama": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Ollama local benchmark",
                "options": {"baseURL": "http://127.0.0.1:11434/v1"},
                "models": {model: {"name": model}},
            }
        },
        "tools": {
            "bash": False,
            "edit": False,
            "write": False,
            "webfetch": False,
            "websearch": False,
        },
        "mcp": mcp,
    }
    path = workspace / "opencode.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _collect_events(raw: str) -> tuple[str, int, int, int]:
    texts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    tool_ids: set[str] = set()
    tool_fallback = 0

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            texts.append(line)
            continue
        for item in _walk(event):
            item_type = str(item.get("type", "")).casefold()
            text = item.get("text")
            if isinstance(text, str) and ("text" in item_type or item_type in {"", "content"}):
                texts.append(text)
            if item_type == "tool" or "tool-call" in item_type or "tool_call" in item_type:
                identifier = item.get("id") or item.get("callID") or item.get("toolCallId")
                if identifier:
                    tool_ids.add(str(identifier))
                else:
                    tool_fallback += 1
            tokens = item.get("tokens")
            if isinstance(tokens, dict):
                for key in ("input", "prompt", "input_tokens", "prompt_tokens"):
                    if isinstance(tokens.get(key), int):
                        input_tokens = max(input_tokens, int(tokens[key]))
                for key in ("output", "completion", "output_tokens", "completion_tokens"):
                    if isinstance(tokens.get(key), int):
                        output_tokens = max(output_tokens, int(tokens[key]))
            usage = item.get("usage")
            if isinstance(usage, dict):
                for key in ("input_tokens", "prompt_tokens"):
                    if isinstance(usage.get(key), int):
                        input_tokens = max(input_tokens, int(usage[key]))
                for key in ("output_tokens", "completion_tokens"):
                    if isinstance(usage.get(key), int):
                        output_tokens = max(output_tokens, int(usage[key]))

    return "\n".join(texts), input_tokens, output_tokens, len(tool_ids) + tool_fallback


def _balanced_objects(text: str) -> Iterable[str]:
    for start, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : index + 1]
                    break


def _find_response(*texts: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for text in texts:
        for raw in _balanced_objects(text):
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and REQUIRED_KEYS.issubset(value):
                candidates.append(value)
    return candidates[-1] if candidates else None


def _prompt_value(prompt: str, label: str, default: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+?)\s*$", prompt, flags=re.MULTILINE)
    return match.group(1).strip() if match else default


def _error_response(prompt: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "case_id": _prompt_value(prompt, "Case ID", "unknown"),
        "status": "error",
        "region": _prompt_value(prompt, "Region", "us-east-1"),
        "currency": "USD",
        "price_effective_at": None,
        "monthly_total_usd": None,
        "service_estimates": [],
        "assumptions": [],
        "excluded_costs": [],
        "missing_inputs": [],
        "confidence": 0.0,
        "summary": detail[:2000] or "OpenCode did not produce a parseable benchmark response.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    prompt = sys.stdin.read()
    workspace = Path.cwd().resolve()
    repo_root = Path(
        os.environ.get("AWS_ABLATION_REPO_ROOT", Path(__file__).resolve().parents[2])
    ).resolve()

    if _contains(args.condition, "skill"):
        _copy_skill(repo_root, workspace)
    config_path = _write_config(workspace, args.condition, args.model, repo_root)

    benchmark_instructions = f"""
BENCHMARK CONTROL (same task across all ablation conditions):
- Work read-only. Inspect TASK.md and every file under input/ before answering.
- Do not deploy or modify any AWS resource or local input file.
- If a skill named deploy is available, load it exactly once with the skill tool before solving.
- If aws_knowledge MCP tools are available, use at most two calls to validate AWS service/pricing dimensions.
- If frozen_pricing MCP tools are available, call get_case_price_dimensions once using the Case ID.
- Do the arithmetic yourself from the usage profile; a tool never supplies the hidden expected total.
- Your final assistant message must contain only one JSON object matching agent-output.schema.json.
- Do not include Markdown fences or commentary around the JSON.

{prompt}
""".strip()

    raw_path = workspace / "opencode-events.jsonl"
    stderr_path = workspace / "opencode-stderr.txt"
    env = os.environ.copy()
    env.update(
        {
            "OPENCODE_CONFIG": str(config_path),
            "OPENCODE_AUTO_SHARE": "false",
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
            "NO_COLOR": "1",
        }
    )
    command = [
        "opencode",
        "run",
        "--dir",
        str(workspace),
        "--model",
        f"ollama/{args.model}",
        "--format",
        "json",
        "--dangerously-skip-permissions",
        "--title",
        f"aws-ablation-{args.condition}-{_prompt_value(prompt, 'Case ID', 'unknown')}",
        benchmark_instructions,
    ]

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=env,
            timeout=280,
            check=False,
        )
        raw = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        raw = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        exit_code = 124

    raw_path.write_text(raw, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    (workspace / "opencode-exit-code.txt").write_text(str(exit_code) + "\n", encoding="utf-8")

    text, input_tokens, output_tokens, tool_calls = _collect_events(raw)
    response = _find_response(text, raw)
    if response is None:
        response = _error_response(
            prompt,
            f"OpenCode exit={exit_code}; no parseable final JSON. stderr={stderr[-1200:]}",
        )

    if input_tokens == 0:
        input_tokens = max(1, len(benchmark_instructions) // 4)
    if output_tokens == 0:
        output_tokens = max(1, len(json.dumps(response, ensure_ascii=False)) // 4)
    response["agent_metrics"] = {
        "model": args.model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model_cost_usd": 0.0,
        "tool_calls": tool_calls,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
