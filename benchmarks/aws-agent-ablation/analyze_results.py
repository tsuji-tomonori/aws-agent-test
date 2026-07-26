from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from aws_agent_eval.dataset import load_dataset


def percentage(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def check_pass(evaluation: dict[str, Any], code: str) -> bool:
    for check in evaluation.get("checks", []):
        if check.get("code") == code:
            return bool(check.get("passed"))
    return False


def parse_identity(name: str) -> tuple[str, str]:
    model, condition = name.split("__", 1)
    return model, condition.replace("-", "+") if condition.startswith("skill-") else condition


def normalise_service(value: str) -> str:
    aliases = {
        "lambda": "aws lambda",
        "amazon lambda": "aws lambda",
        "api gateway": "amazon api gateway",
        "dynamodb": "amazon dynamodb",
        "s3": "amazon s3",
        "cloudfront": "amazon cloudfront",
        "fargate": "aws fargate",
        "alb": "elastic load balancing",
        "application load balancer": "elastic load balancing",
        "elastic load balancing v2": "elastic load balancing",
    }
    normalized = " ".join(value.casefold().replace("_", " ").replace("-", " ").split())
    return aliases.get(normalized, normalized)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    dataset = load_dataset(repo_root / "datasets/aws-cost-v1")
    oracle = {case.id: case.data["oracle"]["monthly_total_usd"] for case in dataset.cases}
    expected_services = {
        case.id: {
            normalise_service(str(value))
            for value in case.data["expected"]["required_services"]
        }
        for case in dataset.cases
    }

    rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    for result_path in sorted((root / "runs").glob("*/results.json")):
        model, condition = parse_identity(result_path.parent.name)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        summary = result["summary"]
        relative_errors: list[float] = []
        tool_calls: list[float] = []
        input_tokens: list[float] = []
        output_tokens: list[float] = []
        coverage_ratios: list[float] = []
        check_rates: dict[str, list[bool]] = defaultdict(list)
        for trial in result["trials"]:
            response = trial.get("response") or {}
            evaluation = trial["evaluation"]
            case_id = trial["case_id"]
            metrics = response.get("agent_metrics") or {}
            tool_calls.append(float(metrics.get("tool_calls", 0)))
            input_tokens.append(float(metrics.get("input_tokens", 0)))
            output_tokens.append(float(metrics.get("output_tokens", 0)))
            actual = response.get("monthly_total_usd")
            expected_total = oracle.get(case_id)
            if (
                isinstance(actual, (int, float))
                and isinstance(expected_total, (int, float))
                and expected_total
            ):
                relative_errors.append(
                    abs(float(actual) - float(expected_total)) / float(expected_total)
                )
            estimated = {
                normalise_service(str(item.get("service")))
                for item in response.get("service_estimates", [])
                if isinstance(item, dict)
            }
            required = expected_services.get(case_id, set())
            if required:
                coverage_ratios.append(len(required & estimated) / len(required))
            elif response.get("status") == "needs_clarification":
                coverage_ratios.append(1.0)
            for code in (
                "schema_valid",
                "status_match",
                "service_coverage",
                "service_ranges",
                "total_range",
                "arithmetic_consistency",
                "required_source_urls",
                "missing_input_coverage",
                "no_fabricated_estimate",
            ):
                check_rates[code].append(check_pass(evaluation, code))
            trial_rows.append(
                {
                    "model": model,
                    "condition": condition,
                    "case_id": case_id,
                    "trial": trial["trial"],
                    "passed": evaluation["passed"],
                    "score": evaluation["score"],
                    "latency_seconds": trial["execution"]["duration_seconds"],
                    "tool_calls": metrics.get("tool_calls", 0),
                    "input_tokens": metrics.get("input_tokens", 0),
                    "output_tokens": metrics.get("output_tokens", 0),
                    "status": response.get("status"),
                    "monthly_total_usd": actual,
                    "relative_error": (
                        abs(float(actual) - float(expected_total)) / float(expected_total)
                        if isinstance(actual, (int, float))
                        and isinstance(expected_total, (int, float))
                        and expected_total
                        else None
                    ),
                    "critical_failures": ",".join(evaluation.get("critical_failures", [])),
                }
            )

        row: dict[str, Any] = {
            "model": model,
            "condition": condition,
            "trials": summary["trials"],
            "successes": summary["successes"],
            "success_rate": summary["success_rate"],
            "wilson_lower": summary["wilson_95"]["lower"],
            "wilson_upper": summary["wilson_95"]["upper"],
            "pass_at_k": summary["pass_at_k"],
            "pass_power_k": summary["pass_power_k"],
            "average_score": summary["average_score"],
            "average_latency_seconds": summary["average_latency_seconds"],
            "mean_absolute_percentage_error": mean(relative_errors) if relative_errors else None,
            "mean_service_coverage": mean(coverage_ratios) if coverage_ratios else None,
            "mean_tool_calls": mean(tool_calls) if tool_calls else 0.0,
            "mean_input_tokens": mean(input_tokens) if input_tokens else 0.0,
            "mean_output_tokens": mean(output_tokens) if output_tokens else 0.0,
        }
        for code, values in check_rates.items():
            row[f"{code}_rate"] = sum(values) / len(values) if values else None
        rows.append(row)

    baselines = {row["model"]: row for row in rows if row["condition"] == "baseline"}
    for row in rows:
        baseline = baselines.get(row["model"])
        if baseline:
            row["success_rate_delta_vs_baseline"] = (
                row["success_rate"] - baseline["success_rate"]
            )
            row["score_delta_vs_baseline"] = (
                row["average_score"] - baseline["average_score"]
            )
            row["latency_ratio_vs_baseline"] = (
                row["average_latency_seconds"] / baseline["average_latency_seconds"]
                if baseline["average_latency_seconds"]
                else None
            )
            base_mape = baseline["mean_absolute_percentage_error"]
            row["mape_delta_vs_baseline"] = (
                row["mean_absolute_percentage_error"] - base_mape
                if row["mean_absolute_percentage_error"] is not None
                and base_mape is not None
                else None
            )

    (root / "ablation-summary.json").write_text(
        json.dumps(
            {"conditions": rows, "trials": trial_rows},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    fieldnames = sorted({key for row in rows for key in row})
    with (root / "ablation-summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    trial_fields = sorted({key for row in trial_rows for key in row})
    with (root / "ablation-trials.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=trial_fields)
        writer.writeheader()
        writer.writerows(trial_rows)

    lines = [
        "# AWS Agent ablation benchmark",
        "",
        "## Experimental boundary",
        "",
        "- `skill` is the official `deploy-on-aws` deploy skill pinned at commit `089861a4596343c2b8135cc4f7cc68655a081864`.",
        "- `knowledge` is the genuine managed AWS Knowledge MCP endpoint `https://knowledge-mcp.global.api.aws`.",
        "- `pricing` is a local MCP exposing frozen public unit prices only. It is a controlled surrogate for price-tool value, not the authenticated official AWS Pricing MCP.",
        "- No condition receives oracle totals, expected ranges, or evaluator results.",
        "",
        "## Condition summary",
        "",
        "| Model | Condition | Trials | Success (Wilson 95%) | pass^k | Score | MAPE | Coverage | Latency | Tools | Δ success | Latency × |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {condition} | {trials} | {success} | {power} | {score:.1f} | {mape} | {coverage} | {latency:.2f}s | {tools:.2f} | {delta} | {ratio} |".format(
                model=row["model"],
                condition=row["condition"],
                trials=row["trials"],
                success=(
                    f"{percentage(row['success_rate'])} "
                    f"({percentage(row['wilson_lower'])}–{percentage(row['wilson_upper'])})"
                ),
                power=percentage(row["pass_power_k"]),
                score=row["average_score"],
                mape=percentage(row["mean_absolute_percentage_error"]),
                coverage=percentage(row["mean_service_coverage"]),
                latency=row["average_latency_seconds"],
                tools=row["mean_tool_calls"],
                delta=(
                    f"{row.get('success_rate_delta_vs_baseline', 0) * 100:+.1f}pp"
                    if row.get("success_rate_delta_vs_baseline") is not None
                    else "—"
                ),
                ratio=(
                    f"{row.get('latency_ratio_vs_baseline'):.2f}"
                    if row.get("latency_ratio_vs_baseline") is not None
                    else "—"
                ),
            )
        )

    lines.extend(["", "## Deterministic check rates", ""])
    lines.extend(
        [
            "| Model | Condition | Schema | Status | Services | Service range | Total range | Arithmetic | Sources |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| {model} | {condition} | {schema} | {status} | {services} | {service_range} | {total} | {arith} | {sources} |".format(
                model=row["model"],
                condition=row["condition"],
                schema=percentage(row.get("schema_valid_rate")),
                status=percentage(row.get("status_match_rate")),
                services=percentage(row.get("service_coverage_rate")),
                service_range=percentage(row.get("service_ranges_rate")),
                total=percentage(row.get("total_range_rate")),
                arith=percentage(row.get("arithmetic_consistency_rate")),
                sources=percentage(row.get("required_source_urls_rate")),
            )
        )
    lines.append("")
    (root / "ablation-report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
