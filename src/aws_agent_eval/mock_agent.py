from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .utils import dump_json, load_json, utc_now


def build_response(case: dict[str, Any], *, mode: str, trial: int) -> dict[str, Any]:
    expected = case["expected"]
    status = expected["status"]
    retrieved_at = utc_now()

    if status == "needs_clarification":
        response: dict[str, Any] = {
            "schema_version": "1.0",
            "case_id": case["id"],
            "status": "needs_clarification",
            "region": case["region"],
            "currency": case["currency"],
            "price_effective_at": None,
            "monthly_total_usd": None,
            "service_estimates": [],
            "assumptions": [],
            "excluded_costs": ["All costs are deferred until usage inputs are supplied."],
            "missing_inputs": [
                {"id": item, "question": f"Please provide {item.replace('_', ' ')}."}
                for item in expected["required_missing_input_ids"]
            ],
            "confidence": 0.99,
            "summary": "Required usage inputs are missing; no cost was fabricated.",
            "agent_metrics": {"model": "mock", "input_tokens": 0, "output_tokens": 0, "model_cost_usd": 0.0, "tool_calls": 0},
        }
    else:
        estimates = []
        source_titles = {item["url"]: item["title"] for item in case["price_snapshot"]["sources"]}
        for item in case["oracle"]["service_calculations"]:
            estimates.append(
                {
                    "service": item["service"],
                    "resource_ids": [],
                    "monthly_cost_usd": item["monthly_cost_usd"],
                    "formula": item["formula"],
                    "pricing_dimensions": [
                        {
                            "name": component["name"],
                            "quantity": component["quantity"],
                            "unit": component["unit"],
                            "unit_price_usd": component["unit_price_usd"],
                        }
                        for component in item["components"]
                    ],
                    "sources": [
                        {
                            "title": source_titles[item["source_url"]],
                            "url": item["source_url"],
                            "retrieved_at": retrieved_at,
                        }
                    ],
                }
            )
        total = case["oracle"]["monthly_total_usd"]
        response = {
            "schema_version": "1.0",
            "case_id": case["id"],
            "status": status,
            "region": case["region"],
            "currency": case["currency"],
            "price_effective_at": case["price_snapshot"]["effective_at"],
            "monthly_total_usd": total,
            "service_estimates": estimates,
            "assumptions": [
                {"id": item, "statement": f"Mock records required assumption: {item}.", "impact": "medium"}
                for item in expected["required_assumption_ids"]
            ],
            "excluded_costs": ["Tax, support, and account-specific discounts are excluded."],
            "missing_inputs": [],
            "confidence": 0.95,
            "summary": "Deterministic mock response for harness verification.",
            "agent_metrics": {"model": "mock", "input_tokens": 0, "output_tokens": 0, "model_cost_usd": 0.0, "tool_calls": 0},
        }

    if mode == "flaky" and trial % 3 == 0:
        if response["status"] == "completed" and response["service_estimates"]:
            response["service_estimates"] = response["service_estimates"][:-1]
        else:
            response["missing_inputs"] = []
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["good", "flaky"], default="good")
    args = parser.parse_args()
    trial = int(os.environ.get("AWS_AGENT_EVAL_TRIAL", "1"))
    response = build_response(load_json(args.case_file), mode=args.mode, trial=trial)
    dump_json(args.output, response)


if __name__ == "__main__":
    main()
