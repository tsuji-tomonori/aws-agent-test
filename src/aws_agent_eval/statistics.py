from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean

from .types import JsonObject


def wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def summarise_trials(trials: list[JsonObject], repetitions: int) -> JsonObject:
    total = len(trials)
    successes = sum(bool(item["evaluation"]["passed"]) for item in trials)
    lower, upper = wilson_interval(successes, total)

    by_case: dict[str, list[bool]] = defaultdict(list)
    scores: list[float] = []
    latencies: list[float] = []
    model_costs: list[float] = []
    failures: dict[str, int] = defaultdict(int)

    for item in trials:
        evaluation = item["evaluation"]
        by_case[str(item["case_id"])].append(bool(evaluation["passed"]))
        scores.append(float(evaluation["score"]))
        latencies.append(float(item["execution"]["duration_seconds"]))
        for failure in evaluation["critical_failures"]:
            failures[str(failure)] += 1
        response = item.get("response")
        if isinstance(response, dict):
            metrics = response.get("agent_metrics")
            if isinstance(metrics, dict) and isinstance(
                metrics.get("model_cost_usd"), (int, float)
            ):
                model_costs.append(float(metrics["model_cost_usd"]))

    any_success = sum(any(values) for values in by_case.values())
    all_success = sum(len(values) == repetitions and all(values) for values in by_case.values())
    case_count = len(by_case)
    return {
        "trials": total,
        "successes": successes,
        "success_rate": round(successes / total, 6) if total else 0.0,
        "wilson_95": {"lower": round(lower, 6), "upper": round(upper, 6)},
        "case_count": case_count,
        "repetitions": repetitions,
        "pass_at_k": round(any_success / case_count, 6) if case_count else 0.0,
        "pass_power_k": round(all_success / case_count, 6) if case_count else 0.0,
        "average_score": round(mean(scores), 3) if scores else 0.0,
        "average_latency_seconds": round(mean(latencies), 3) if latencies else 0.0,
        "reported_model_cost_usd": round(sum(model_costs), 6) if model_costs else None,
        "failure_counts": dict(sorted(failures.items())),
    }
