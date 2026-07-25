from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .assets import materialize_cached_assets, public_asset_prompt_items
from .dataset import default_schema_dir
from .evaluator import evaluate_response
from .prompt import render_agent_prompt
from .schema import validate_object
from .statistics import summarise_trials
from .types import Case, Dataset, JsonObject
from .utils import (
    canonical_digest,
    dump_json,
    extract_json_object,
    load_json,
    safe_relative,
    utc_now,
)


def load_profile(profile_path: Path, schema_dir: Path | None = None) -> JsonObject:
    profile = load_json(profile_path)
    schemas = schema_dir or default_schema_dir()
    validate_object(profile, schemas / "profile.schema.json", label=str(profile_path))
    return profile


def run_experiment(
    dataset: Dataset,
    profile: JsonObject,
    run_dir: Path,
    *,
    repetitions: int,
    selected_case_ids: set[str] | None = None,
    prompt_template: Path | None = None,
    asset_cache: Path | None = None,
) -> JsonObject:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    template = (
        prompt_template or Path(__file__).resolve().parents[2] / "prompts/agent-cost-estimation.md"
    )
    schema_path = default_schema_dir() / "agent-output.schema.json"

    cases = [
        case for case in dataset.cases if not selected_case_ids or case.id in selected_case_ids
    ]
    if selected_case_ids:
        found = {case.id for case in cases}
        unknown = selected_case_ids - found
        if unknown:
            raise ValueError(f"Unknown case ids: {sorted(unknown)}")

    started_at = utc_now()
    trials: list[JsonObject] = []
    for case in cases:
        for trial in range(1, repetitions + 1):
            trials.append(
                _run_trial(
                    dataset,
                    case,
                    profile,
                    run_dir,
                    trial=trial,
                    prompt_template=template,
                    schema_path=schema_path,
                    asset_cache=asset_cache,
                )
            )

    result: JsonObject = {
        "schema_version": "1.0",
        "dataset": {
            "id": dataset.id,
            "version": dataset.version,
            "digest": canonical_digest(dataset.data),
        },
        "profile": {
            "name": profile["name"],
            "digest": canonical_digest(profile),
        },
        "repetitions": repetitions,
        "started_at": started_at,
        "completed_at": utc_now(),
        "trials": trials,
        "summary": summarise_trials(trials, repetitions),
    }
    dump_json(run_dir / "results.json", result)
    return result


def _run_trial(
    dataset: Dataset,
    case: Case,
    profile: JsonObject,
    run_dir: Path,
    *,
    trial: int,
    prompt_template: Path,
    schema_path: Path,
    asset_cache: Path | None,
) -> JsonObject:
    workspace = run_dir / "workspaces" / case.id / f"trial-{trial:02d}"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    for input_ref in case.data["inputs"]:
        relative = safe_relative(str(input_ref))
        source = case.path.parent / relative
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    workspace_schema = workspace / "agent-output.schema.json"
    shutil.copy2(schema_path, workspace_schema)

    public_assets = (
        materialize_cached_assets(dataset, case, asset_cache, workspace)
        if asset_cache is not None
        else public_asset_prompt_items(case)
    )
    prompt = render_agent_prompt(case, prompt_template, public_assets)
    (workspace / "TASK.md").write_text(prompt, encoding="utf-8")
    output_file = workspace / "response.json"
    stdout_file = workspace / "stdout.txt"
    stderr_file = workspace / "stderr.txt"

    variables = {
        "workspace": str(workspace),
        "output_file": str(output_file),
        "schema_file": str(workspace_schema),
        "case_file": str(case.path),
        "case_id": case.id,
        "trial": str(trial),
    }
    command = [_interpolate(str(token), variables) for token in profile["command"]]
    environment = os.environ.copy()
    environment.update(
        {key: _interpolate(str(value), variables) for key, value in profile["environment"].items()}
    )
    environment["AWS_AGENT_EVAL_CASE_ID"] = case.id
    environment["AWS_AGENT_EVAL_TRIAL"] = str(trial)

    started = time.monotonic()
    return_code: int | None = None
    timed_out = False
    execution_error: str | None = None
    stdout = ""
    stderr = ""
    response: JsonObject | None = None
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=workspace,
            env=environment,
            timeout=int(profile["timeout_seconds"]),
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        if completed.returncode != 0:
            execution_error = f"command exited with code {completed.returncode}"
        else:
            response = _parse_response(str(profile["parser"]), stdout, output_file)
            dump_json(output_file, response)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        execution_error = f"command timed out after {profile['timeout_seconds']} seconds"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        execution_error = f"{type(exc).__name__}: {exc}"
    duration = time.monotonic() - started
    stdout_file.write_text(stdout, encoding="utf-8")
    stderr_file.write_text(stderr, encoding="utf-8")

    evaluation = evaluate_response(
        case,
        response,
        trial=trial,
        execution_error=execution_error,
        schema_path=schema_path,
    )
    record: JsonObject = {
        "case_id": case.id,
        "trial": trial,
        "workspace": str(workspace.relative_to(run_dir)),
        "execution": {
            "command": command,
            "return_code": return_code,
            "timed_out": timed_out,
            "duration_seconds": round(duration, 6),
            "error": execution_error,
        },
        "response": response,
        "evaluation": evaluation,
    }
    dump_json(workspace / "result.json", record)
    return record


def _parse_response(parser: str, stdout: str, output_file: Path) -> JsonObject:
    if parser == "output-file-json":
        if not output_file.exists():
            raise ValueError(f"Agent did not create output file: {output_file}")
        return load_json(output_file)
    if parser == "stdout-json":
        return extract_json_object(stdout)
    if parser == "claude-json":
        outer = extract_json_object(stdout)
        result = outer.get("result")
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            return extract_json_object(result)
        raise ValueError("Claude JSON output does not contain a result object/string")
    raise ValueError(f"Unsupported parser: {parser}")


def _interpolate(value: str, variables: dict[str, str]) -> str:
    rendered = value
    for key, replacement in variables.items():
        rendered = rendered.replace("{" + key + "}", replacement)
    return rendered


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)
