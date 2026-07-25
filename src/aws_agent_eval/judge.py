from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import median

from .dataset import default_schema_dir
from .schema import validate_object
from .types import JsonObject
from .utils import dump_json, load_json


def prepare_judge_batch(run_dir: Path, repeats: int, *, seed: int = 20260725) -> Path:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    results = load_json(run_dir / "results.json")
    items: list[JsonObject] = []
    for trial in results["trials"]:
        if not isinstance(trial, dict) or not isinstance(trial.get("response"), dict):
            continue
        for repeat in range(1, repeats + 1):
            item_id = f"{trial['case_id']}:trial-{int(trial['trial']):02d}"
            items.append(
                {
                    "judge_item_id": item_id,
                    "repeat": repeat,
                    "task_context": {
                        "case_id": trial["case_id"],
                        "deterministic_pass": trial["evaluation"]["passed"],
                        "critical_failures": trial["evaluation"]["critical_failures"],
                    },
                    "agent_response": trial["response"],
                }
            )
    random.Random(seed).shuffle(items)
    judge_dir = run_dir / "judge"
    judge_dir.mkdir(parents=True, exist_ok=True)
    path = judge_dir / "batch.jsonl"
    with path.open("w", encoding="utf-8") as stream:
        for item in items:
            stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def aggregate_judgments(run_dir: Path, input_path: Path) -> Path:
    schema_path = default_schema_dir() / "judge-output.schema.json"
    grouped: dict[str, list[JsonObject]] = defaultdict(list)
    with input_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")
            validate_object(value, schema_path, label=f"{input_path}:{line_number}")
            grouped[str(value["judge_item_id"])].append(value)

    aggregates: list[JsonObject] = []
    dimensions = [
        "assumption_clarity",
        "uncertainty_handling",
        "exclusion_clarity",
        "actionability",
    ]
    for item_id, values in sorted(grouped.items()):
        scores = {
            dimension: median(float(value["scores"][dimension]) for value in values)
            for dimension in dimensions
        }
        pass_votes = sum(bool(value["semantic_pass"]) for value in values)
        concerns = [str(value["critical_concern"]) for value in values if value["critical_concern"]]
        aggregates.append(
            {
                "judge_item_id": item_id,
                "judgments": len(values),
                "median_scores": scores,
                "semantic_pass_majority": pass_votes > len(values) / 2,
                "critical_concerns": concerns,
            }
        )
    output = run_dir / "judge" / "aggregate.json"
    dump_json(output, {"items": aggregates})
    return output
