from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.report import generate_report
from aws_agent_eval.runner import run_experiment

CASES = {
    "cfn-serverless-api",
    "cfn-static-site",
    "cdk-fargate-alb",
    "cfn-missing-usage",
}

RUNS = [
    {
        "model_alias": "qwen25-05b-q4",
        "model": "qwen2.5:0.5b-instruct-q4_0",
        "repetitions": 2,
        "conditions": [
            "baseline",
            "skill",
            "knowledge",
            "skill+knowledge",
            "pricing",
            "skill+pricing",
        ],
    },
    {
        "model_alias": "gemma3-1b-q4",
        "model": "gemma3:1b",
        "repetitions": 1,
        "conditions": ["baseline", "skill", "pricing", "skill+pricing"],
    },
]


def version(command: list[str]) -> str:
    try:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset(repo_root / "datasets/aws-cost-v1")
    metadata = {
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "opencode": version(["opencode", "--version"]),
        "ollama": version(["ollama", "--version"]),
        "dataset": {"id": dataset.id, "version": dataset.version},
        "cases": sorted(CASES),
        "aws_agent_skill_commit": "089861a4596343c2b8135cc4f7cc68655a081864",
        "aws_agent_skill_source": os.environ.get(
            "AWS_AGENT_SKILL_SOURCE",
            str(repo_root / "benchmarks/aws-agent-ablation/skills/deploy"),
        ),
        "aws_knowledge_mcp": "https://knowledge-mcp.global.api.aws",
        "pricing_mcp_mode": "frozen-public-unit-price surrogate; no oracle totals",
    }
    (output / "environment.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    wrapper = repo_root / "benchmarks/aws-agent-ablation/opencode_agent.py"
    for spec in RUNS:
        for condition in spec["conditions"]:
            slug = condition.replace("+", "-")
            run_dir = output / "runs" / f"{spec['model_alias']}__{slug}"
            profile_environment = {
                "AWS_ABLATION_REPO_ROOT": str(repo_root),
                "AWS_EC2_METADATA_DISABLED": "true",
            }
            if os.environ.get("AWS_AGENT_SKILL_SOURCE"):
                profile_environment["AWS_AGENT_SKILL_SOURCE"] = os.environ[
                    "AWS_AGENT_SKILL_SOURCE"
                ]
            profile = {
                "schema_version": "1.0",
                "name": f"opencode-{spec['model_alias']}-{slug}",
                "kind": "command",
                "command": [
                    sys.executable,
                    str(wrapper),
                    "--output",
                    "{output_file}",
                    "--condition",
                    condition,
                    "--model",
                    spec["model"],
                ],
                "parser": "output-file-json",
                "timeout_seconds": 300,
                "environment": profile_environment,
                "required_commands": ["python", "opencode", "ollama"],
                "required_environment": [],
            }
            run_experiment(
                dataset,
                profile,
                run_dir,
                repetitions=int(spec["repetitions"]),
                selected_case_ids=CASES,
            )
            generate_report(run_dir)

    subprocess.run(
        [
            sys.executable,
            str(repo_root / "benchmarks/aws-agent-ablation/analyze_results.py"),
            "--root",
            str(output),
        ],
        check=True,
        env={**os.environ, "AWS_ABLATION_REPO_ROOT": str(repo_root)},
    )


if __name__ == "__main__":
    main()
