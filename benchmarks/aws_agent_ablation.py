#!/usr/bin/env python3
"""Controlled ablation of AWS Agent skills and pricing-tool context.

This benchmark intentionally separates four conditions while keeping the model,
case, prompt contract, generation parameters, and evaluator fixed:

- baseline: no AWS Agent skill, no pricing tool result
- skill: pinned AWS deploy-on-aws skill context only
- pricing: frozen, public-price pricing-tool result only
- skill_pricing: both skill and pricing-tool result

The pricing condition is not a live AWS Pricing MCP API call. It is a frozen
adapter that reproduces the *information boundary* of the awspricing tool using
unit prices already versioned by aws-agent-test. It avoids AWS credentials and
never reveals oracle totals or expected pass ranges.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.evaluator import evaluate_response
from aws_agent_eval.statistics import summarise_trials
from aws_agent_eval.types import Case, JsonObject
from aws_agent_eval.utils import dump_json, extract_json_object


DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_CASES = (
    "cfn-serverless-api",
    "cfn-static-site",
    "cdk-fargate-alb",
    "cfn-missing-usage",
)
CONDITIONS = ("baseline", "skill", "pricing", "skill_pricing")
PINNED_SKILL_COMMIT = "089861a4596343c2b8135cc4f7cc68655a081864"
PINNED_SKILL_SHA = "894e28ef7a82475db14c8ca77098cbe33904fb80"
PINNED_COST_REFERENCE_SHA = "48946df66c9a9160231227d35de526359c3f048d"


VENDORED_SKILL_ROOT = Path(__file__).resolve().parent / "vendor/aws-deploy-skill"




def git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    framed = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git object identity, not security.


def validate_experiment_inputs(dataset_path: Path, case_ids: list[str]) -> None:
    skill_path = VENDORED_SKILL_ROOT / "SKILL.md"
    reference_path = VENDORED_SKILL_ROOT / "references/cost-estimation.md"
    actual_skill_sha = git_blob_sha(skill_path)
    actual_reference_sha = git_blob_sha(reference_path)
    if actual_skill_sha != PINNED_SKILL_SHA:
        raise ValueError(
            f"Pinned skill SHA mismatch: {actual_skill_sha} != {PINNED_SKILL_SHA}"
        )
    if actual_reference_sha != PINNED_COST_REFERENCE_SHA:
        raise ValueError(
            "Pinned cost-reference SHA mismatch: "
            f"{actual_reference_sha} != {PINNED_COST_REFERENCE_SHA}"
        )

    dataset = load_dataset(dataset_path)
    case_index = {case.id: case for case in dataset.cases}
    for case_id in case_ids:
        if case_id not in case_index:
            raise ValueError(f"Unknown case: {case_id}")
        if case_id not in FROZEN_PRICING:
            raise ValueError(f"Missing frozen pricing fixture: {case_id}")
        visible = read_visible_case(case_index[case_id])
        forbidden = {"oracle", "expected", "price_snapshot", "official_reference"}
        leaked = forbidden.intersection(visible)
        if leaked:
            raise ValueError(f"Hidden evaluator fields leaked for {case_id}: {sorted(leaked)}")
        serialized_pricing = json.dumps(FROZEN_PRICING[case_id], sort_keys=True)
        oracle = case_index[case_id].data.get("oracle")
        if isinstance(oracle, dict) and oracle.get("monthly_total_usd") is not None:
            marker = json.dumps(oracle["monthly_total_usd"])
            if f'"monthly_total_usd": {marker}' in serialized_pricing:
                raise ValueError(f"Oracle total leaked into pricing fixture for {case_id}")

def load_pinned_skill_context() -> str:
    """Load the exact pinned upstream Skill and its cost-estimation reference."""
    skill = (VENDORED_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    cost_reference = (
        VENDORED_SKILL_ROOT / "references/cost-estimation.md"
    ).read_text(encoding="utf-8")
    return (
        "OFFICIAL AWS DEPLOY-ON-AWS SKILL (PINNED UPSTREAM CONTENT)\n\n"
        + skill
        + "\n\nPINNED COST-ESTIMATION REFERENCE\n\n"
        + cost_reference
    )


# Frozen unit-price results. These values are inputs to the model only in pricing
# conditions. They contain no oracle monthly totals and no expected pass ranges.
FROZEN_PRICING: dict[str, list[dict[str, Any]]] = {
    "cfn-serverless-api": [
        {
            "service": "AWS Lambda",
            "dimension": "requests",
            "unit": "million requests",
            "unit_price_usd": 0.20,
            "source_url": "https://aws.amazon.com/lambda/pricing/",
        },
        {
            "service": "AWS Lambda",
            "dimension": "compute",
            "unit": "GB-second",
            "unit_price_usd": 0.0000166667,
            "source_url": "https://aws.amazon.com/lambda/pricing/",
        },
        {
            "service": "Amazon API Gateway",
            "dimension": "HTTP API requests",
            "unit": "million requests",
            "unit_price_usd": 1.0,
            "source_url": "https://aws.amazon.com/api-gateway/pricing/",
        },
        {
            "service": "Amazon DynamoDB",
            "dimension": "write request units",
            "unit": "million WRU",
            "unit_price_usd": 0.625,
            "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/",
        },
        {
            "service": "Amazon DynamoDB",
            "dimension": "read request units",
            "unit": "million RRU",
            "unit_price_usd": 0.125,
            "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/",
        },
    ],
    "cfn-static-site": [
        {
            "service": "Amazon S3",
            "dimension": "Standard storage",
            "unit": "GB-month",
            "unit_price_usd": 0.023,
            "source_url": "https://aws.amazon.com/s3/pricing/",
        },
        {
            "service": "Amazon S3",
            "dimension": "PUT requests",
            "unit": "thousand requests",
            "unit_price_usd": 0.005,
            "source_url": "https://aws.amazon.com/s3/pricing/",
        },
        {
            "service": "Amazon S3",
            "dimension": "GET requests",
            "unit": "thousand requests",
            "unit_price_usd": 0.0004,
            "source_url": "https://aws.amazon.com/s3/pricing/",
        },
        {
            "service": "Amazon CloudFront",
            "dimension": "US/Canada/Mexico transfer out",
            "unit": "GB",
            "unit_price_usd": 0.085,
            "source_url": "https://aws.amazon.com/cloudfront/pricing/",
        },
        {
            "service": "Amazon CloudFront",
            "dimension": "HTTPS requests",
            "unit": "ten-thousand requests",
            "unit_price_usd": 0.01,
            "source_url": "https://aws.amazon.com/cloudfront/pricing/",
        },
    ],
    "cdk-fargate-alb": [
        {
            "service": "AWS Fargate",
            "dimension": "vCPU",
            "unit": "vCPU-hour",
            "unit_price_usd": 0.04048,
            "source_url": "https://aws.amazon.com/fargate/pricing/",
        },
        {
            "service": "AWS Fargate",
            "dimension": "memory",
            "unit": "GB-hour",
            "unit_price_usd": 0.004445,
            "source_url": "https://aws.amazon.com/fargate/pricing/",
        },
        {
            "service": "Elastic Load Balancing",
            "dimension": "ALB hours",
            "unit": "ALB-hour",
            "unit_price_usd": 0.0225,
            "source_url": "https://aws.amazon.com/elasticloadbalancing/pricing/",
        },
        {
            "service": "Elastic Load Balancing",
            "dimension": "LCU hours",
            "unit": "LCU-hour",
            "unit_price_usd": 0.008,
            "source_url": "https://aws.amazon.com/elasticloadbalancing/pricing/",
        },
    ],
    "cfn-missing-usage": [
        {
            "service": "AWS Lambda",
            "dimension": "requests and compute",
            "unit": "usage-dependent",
            "unit_price_usd": None,
            "source_url": "https://aws.amazon.com/lambda/pricing/",
            "note": "A monthly estimate still requires request count and average duration.",
        },
        {
            "service": "Amazon API Gateway",
            "dimension": "HTTP API requests",
            "unit": "usage-dependent",
            "unit_price_usd": None,
            "source_url": "https://aws.amazon.com/api-gateway/pricing/",
            "note": "A monthly estimate still requires request count.",
        },
        {
            "service": "Amazon DynamoDB",
            "dimension": "on-demand reads and writes",
            "unit": "usage-dependent",
            "unit_price_usd": None,
            "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/",
            "note": "A monthly estimate still requires monthly read and write request units.",
        },
    ],
}


@dataclass(frozen=True)
class Condition:
    name: str
    use_skill: bool
    use_pricing: bool


CONDITION_OBJECTS = {
    "baseline": Condition("baseline", False, False),
    "skill": Condition("skill", True, False),
    "pricing": Condition("pricing", False, True),
    "skill_pricing": Condition("skill_pricing", True, True),
}


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    duration_seconds: float
    tokens_per_second: float


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_visible_case(case: Case) -> JsonObject:
    inputs: dict[str, str] = {}
    for relative_text in case.data["inputs"]:
        relative = Path(str(relative_text))
        inputs[str(relative)] = (case.path.parent / relative).read_text(encoding="utf-8")
    return {
        "id": case.id,
        "title": case.data["title"],
        "iac_type": case.data["iac_type"],
        "region": case.data["region"],
        "currency": case.data["currency"],
        "task": case.data["task"],
        "usage_profile": case.data["usage_profile"],
        "pricing_basis": case.data["pricing_basis"],
        "inputs": inputs,
    }


def compact_contract() -> str:
    return r"""
Return exactly one JSON object and no Markdown. Use this compact contract:
{
  "status": "completed" | "needs_clarification" | "unsupported",
  "monthly_total_usd": number | null,
  "service_estimates": [
    {
      "service": "canonical AWS service name",
      "monthly_cost_usd": number,
      "formula": "auditable arithmetic formula",
      "pricing_dimensions": [
        {"name": "...", "quantity": number, "unit": "...", "unit_price_usd": number}
      ],
      "source_urls": ["https://..."]
    }
  ],
  "assumptions": [{"id": "stable_snake_case_id", "statement": "..."}],
  "excluded_costs": ["..."],
  "missing_inputs": [{"id": "stable_snake_case_id", "question": "..."}],
  "confidence": 0.0,
  "summary": "short explanation"
}

Rules:
- Never deploy or mutate AWS resources.
- Use the supplied usage exactly; do not apply Free Tier unless the case says so.
- monthly_total_usd must equal the sum of service_estimates[].monthly_cost_usd.
- Include every billable service in the requested estimation scope.
- If usage is insufficient, return needs_clarification, no monetary estimate, and
  enumerate every missing usage field with a stable snake_case ID.
- Do all arithmetic explicitly. Do not copy an expected answer or pass range.
""".strip()


def build_messages(case: Case, condition: Condition) -> list[dict[str, str]]:
    system_parts = [
        "You are a small, deterministic, read-only AWS cost-estimation agent.",
        "Carefully inspect the input and calculate rather than guessing.",
    ]
    if condition.use_skill:
        system_parts.append(load_pinned_skill_context())

    user_parts = [
        compact_contract(),
        "\nVISIBLE CASE (hidden oracle, expected ranges, and evaluator metadata were removed):\n"
        + json.dumps(read_visible_case(case), ensure_ascii=False, indent=2, sort_keys=True),
    ]
    if condition.use_pricing:
        user_parts.append(
            "\nFROZEN AWSPRICING-TOOL RESULT\n"
            "This is a credential-free, versioned adapter result containing public unit prices only. "
            "It is not an oracle and does not contain monthly totals or pass ranges.\n"
            + json.dumps(
                {
                    "tool": "awspricing.get_pricing_for_case",
                    "mode": "frozen-public-price-adapter",
                    "effective_at": "2026-07-25",
                    "records": FROZEN_PRICING[case.id],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def load_model(model_id: str) -> tuple[Any, Any]:
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    model.eval()
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer, model


def generate(
    tokenizer: Any,
    model: Any,
    messages: list[dict[str, str]],
    *,
    seed: int,
    max_input_tokens: int,
    max_new_tokens: int,
    temperature: float,
) -> GenerationResult:
    set_seed(seed)
    try:
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except (AttributeError, ValueError):
        rendered = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}" for message in messages
        ) + "\n\nASSISTANT:\n"
    encoded = tokenizer(
        rendered,
        return_tensors="pt",
        truncation=True,
        max_length=max_input_tokens,
    )
    input_tokens = int(encoded["input_ids"].shape[-1])
    started = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=max(temperature, 1e-5),
            top_p=0.9,
            repetition_penalty=1.03,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    duration = time.perf_counter() - started
    new_tokens = generated[0, input_tokens:]
    output_tokens = int(new_tokens.shape[-1])
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return GenerationResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_seconds=duration,
        tokens_per_second=(output_tokens / duration if duration > 0 else 0.0),
    )


def as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def pricing_sources_for_service(case_id: str, service: str) -> list[str]:
    normalized = " ".join(service.casefold().replace("_", " ").replace("-", " ").split())
    urls: list[str] = []
    for record in FROZEN_PRICING.get(case_id, []):
        record_name = " ".join(
            str(record["service"]).casefold().replace("_", " ").replace("-", " ").split()
        )
        # Loose aliases are deliberate because tiny models often shorten AWS names.
        aliases = {
            "lambda": "aws lambda",
            "api gateway": "amazon api gateway",
            "dynamodb": "amazon dynamodb",
            "s3": "amazon s3",
            "cloudfront": "amazon cloudfront",
            "fargate": "aws fargate",
            "alb": "elastic load balancing",
            "application load balancer": "elastic load balancing",
        }
        normalized_name = aliases.get(normalized, normalized)
        normalized_record = aliases.get(record_name, record_name)
        if normalized_name == normalized_record:
            url = str(record["source_url"])
            if url not in urls:
                urls.append(url)
    return urls


def normalize_response(
    case: Case,
    compact: JsonObject,
    generation: GenerationResult,
    condition: Condition,
    model_id: str,
) -> JsonObject:
    status = str(compact.get("status", "error"))
    if status not in {"completed", "needs_clarification", "unsupported", "error"}:
        status = "error"

    service_estimates: list[JsonObject] = []
    raw_estimates = compact.get("service_estimates", [])
    if isinstance(raw_estimates, dict):
        raw_estimates = [raw_estimates]
    if isinstance(raw_estimates, list):
        for raw in raw_estimates:
            if not isinstance(raw, dict):
                continue
            service = str(raw.get("service", "")).strip()
            cost = as_number(raw.get("monthly_cost_usd"))
            formula = str(raw.get("formula", "")).strip()
            if not service or cost is None or not formula:
                continue

            dimensions: list[JsonObject] = []
            raw_dimensions = raw.get("pricing_dimensions", [])
            if isinstance(raw_dimensions, list):
                for dimension in raw_dimensions:
                    if not isinstance(dimension, dict):
                        continue
                    quantity = as_number(dimension.get("quantity"))
                    unit_price = as_number(dimension.get("unit_price_usd"))
                    if quantity is None or unit_price is None:
                        continue
                    dimensions.append(
                        {
                            "name": str(dimension.get("name", "dimension")),
                            "quantity": quantity,
                            "unit": str(dimension.get("unit", "unit")),
                            "unit_price_usd": unit_price,
                        }
                    )

            urls = string_list(raw.get("source_urls", []))
            if condition.use_pricing:
                for url in pricing_sources_for_service(case.id, service):
                    if url not in urls:
                        urls.append(url)
            sources = [
                {"title": url, "url": url, "retrieved_at": utc_now()} for url in urls
            ]
            service_estimates.append(
                {
                    "service": service,
                    "resource_ids": [],
                    "monthly_cost_usd": cost,
                    "formula": formula,
                    "pricing_dimensions": dimensions,
                    "sources": sources,
                }
            )

    assumptions: list[JsonObject] = []
    raw_assumptions = compact.get("assumptions", [])
    if isinstance(raw_assumptions, list):
        for raw in raw_assumptions:
            if isinstance(raw, str):
                identifier = raw.strip()
                statement = raw.strip()
            elif isinstance(raw, dict):
                identifier = str(raw.get("id", "")).strip()
                statement = str(raw.get("statement", identifier)).strip()
            else:
                continue
            if identifier:
                assumptions.append(
                    {"id": identifier, "statement": statement or identifier, "impact": "medium"}
                )

    missing_inputs: list[JsonObject] = []
    raw_missing = compact.get("missing_inputs", [])
    if isinstance(raw_missing, list):
        for raw in raw_missing:
            if isinstance(raw, str):
                identifier = raw.strip()
                question = f"Please provide {identifier.replace('_', ' ')}."
            elif isinstance(raw, dict):
                identifier = str(raw.get("id", "")).strip()
                question = str(raw.get("question", "")).strip()
            else:
                continue
            if identifier and question:
                missing_inputs.append({"id": identifier, "question": question})

    confidence = as_number(compact.get("confidence"))
    if confidence is None:
        confidence = 0.5
    confidence = min(confidence, 1.0)

    monthly_total = as_number(compact.get("monthly_total_usd"))
    if status != "completed":
        monthly_total = None
        service_estimates = []

    return {
        "schema_version": "1.0",
        "case_id": case.id,
        "status": status,
        "region": case.data["region"],
        "currency": case.data["currency"],
        "price_effective_at": "2026-07-25" if condition.use_pricing else None,
        "monthly_total_usd": monthly_total,
        "service_estimates": service_estimates,
        "assumptions": assumptions,
        "excluded_costs": string_list(compact.get("excluded_costs", [])),
        "missing_inputs": missing_inputs,
        "confidence": confidence,
        "summary": str(compact.get("summary") or "Small local-model benchmark response."),
        "agent_metrics": {
            "model": model_id,
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "model_cost_usd": 0.0,
            "tool_calls": 1 if condition.use_pricing else 0,
        },
    }


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def condition_summary(records: list[JsonObject], repetitions: int) -> JsonObject:
    framework_records = [
        {
            "case_id": record["case_id"],
            "execution": {"duration_seconds": record["generation"]["duration_seconds"]},
            "response": record["response"],
            "evaluation": record["evaluation"],
        }
        for record in records
    ]
    summary = summarise_trials(framework_records, repetitions)
    latencies = [float(record["generation"]["duration_seconds"]) for record in records]
    output_tokens = [int(record["generation"]["output_tokens"]) for record in records]
    input_tokens = [int(record["generation"]["input_tokens"]) for record in records]
    token_rates = [float(record["generation"]["tokens_per_second"]) for record in records]
    parse_failures = sum(record["parse_error"] is not None for record in records)
    summary.update(
        {
            "latency_median_seconds": round(statistics.median(latencies), 3) if latencies else 0.0,
            "latency_p95_seconds": round(percentile(latencies, 0.95), 3),
            "input_tokens_average": round(statistics.mean(input_tokens), 1) if input_tokens else 0.0,
            "output_tokens_average": round(statistics.mean(output_tokens), 1) if output_tokens else 0.0,
            "tokens_per_second_average": round(statistics.mean(token_rates), 3) if token_rates else 0.0,
            "parse_failures": parse_failures,
            "tool_calls": sum(
                int((record.get("response") or {}).get("agent_metrics", {}).get("tool_calls", 0))
                for record in records
            ),
        }
    )
    return summary


def write_csv(path: Path, summaries: dict[str, JsonObject]) -> None:
    fields = [
        "condition",
        "trials",
        "successes",
        "success_rate",
        "wilson_lower",
        "wilson_upper",
        "pass_at_k",
        "pass_power_k",
        "average_score",
        "latency_median_seconds",
        "latency_p95_seconds",
        "input_tokens_average",
        "output_tokens_average",
        "tokens_per_second_average",
        "parse_failures",
        "tool_calls",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition in CONDITIONS:
            item = summaries[condition]
            writer.writerow(
                {
                    "condition": condition,
                    "trials": item["trials"],
                    "successes": item["successes"],
                    "success_rate": item["success_rate"],
                    "wilson_lower": item["wilson_95"]["lower"],
                    "wilson_upper": item["wilson_95"]["upper"],
                    "pass_at_k": item["pass_at_k"],
                    "pass_power_k": item["pass_power_k"],
                    "average_score": item["average_score"],
                    "latency_median_seconds": item["latency_median_seconds"],
                    "latency_p95_seconds": item["latency_p95_seconds"],
                    "input_tokens_average": item["input_tokens_average"],
                    "output_tokens_average": item["output_tokens_average"],
                    "tokens_per_second_average": item["tokens_per_second_average"],
                    "parse_failures": item["parse_failures"],
                    "tool_calls": item["tool_calls"],
                }
            )


def markdown_percent(value: Any) -> str:
    return f"{100 * float(value):.1f}%"


def render_report(
    *,
    model_id: str,
    repetitions: int,
    cases: list[str],
    summaries: dict[str, JsonObject],
    records: list[JsonObject],
    started_at: str,
    completed_at: str,
) -> str:
    baseline = summaries["baseline"]
    lines = [
        "# AWS Agent skill / pricing-tool ablation",
        "",
        "## Experiment identity",
        "",
        f"- Model: `{model_id}` (runner-local CPU inference; no model API)",
        f"- Cases: `{', '.join(cases)}`",
        f"- Repetitions per case/condition: `{repetitions}`",
        f"- Started: `{started_at}`",
        f"- Completed: `{completed_at}`",
        f"- Pinned AWS skill commit: `{PINNED_SKILL_COMMIT}`",
        f"- Skill blob SHA: `{PINNED_SKILL_SHA}`",
        f"- Cost-reference blob SHA: `{PINNED_COST_REFERENCE_SHA}`",
        "",
        "## Interpretation boundary",
        "",
        "The `pricing` conditions use a frozen credential-free adapter containing only public unit prices and source URLs. It reproduces the information boundary of the AWS Pricing MCP tool but is **not** a live call to the official AWS Pricing MCP server. No oracle totals or evaluator ranges are supplied to the model. Therefore this run measures the quality benefit of pricing-tool information, not AWS authentication, live API latency, or MCP transport reliability.",
        "",
        "## Aggregate results",
        "",
        "| Condition | Success | pass^k | Avg score | Median latency | p95 latency | Avg input tok | Avg output tok | Tool calls | Δ success vs baseline |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        summary = summaries[condition]
        delta = float(summary["success_rate"]) - float(baseline["success_rate"])
        lines.append(
            f"| `{condition}` | {summary['successes']}/{summary['trials']} ({markdown_percent(summary['success_rate'])}) | "
            f"{markdown_percent(summary['pass_power_k'])} | {summary['average_score']:.2f} | "
            f"{summary['latency_median_seconds']:.3f}s | {summary['latency_p95_seconds']:.3f}s | "
            f"{summary['input_tokens_average']:.1f} | {summary['output_tokens_average']:.1f} | "
            f"{summary['tool_calls']} | {delta * 100:+.1f} pp |"
        )

    lines.extend(["", "## Per-case success", ""])
    lines.append("| Case | " + " | ".join(f"`{condition}`" for condition in CONDITIONS) + " |")
    lines.append("|---|" + "---:|" * len(CONDITIONS))
    for case_id in cases:
        cells = []
        for condition in CONDITIONS:
            selected = [
                record
                for record in records
                if record["case_id"] == case_id and record["condition"] == condition
            ]
            passed = sum(bool(record["evaluation"]["passed"]) for record in selected)
            cells.append(f"{passed}/{len(selected)}")
        lines.append(f"| `{case_id}` | " + " | ".join(cells) + " |")

    lines.extend(["", "## Failure taxonomy", ""])
    for condition in CONDITIONS:
        counts: Counter[str] = Counter()
        for record in records:
            if record["condition"] == condition:
                counts.update(str(value) for value in record["evaluation"]["critical_failures"])
        lines.append(f"### `{condition}`")
        lines.append("")
        if counts:
            lines.extend(["| Failure | Count |", "|---|---:|"])
            for key, value in sorted(counts.items()):
                lines.append(f"| `{key}` | {value} |")
        else:
            lines.append("No critical failures.")
        lines.append("")

    lines.extend(
        [
            "## Conditions",
            "",
            "- `baseline`: case input only.",
            "- `skill`: case input plus the pinned deploy-on-aws cost-estimation guidance.",
            "- `pricing`: case input plus frozen awspricing-style unit-price results.",
            "- `skill_pricing`: both forms of assistance.",
            "",
            "The model and generation settings are fixed. Seeds are paired across conditions, and the execution order is shuffled within each repetition to reduce warm-cache/order bias.",
            "",
        ]
    )
    return "\n".join(lines)


def warm_up(tokenizer: Any, model: Any) -> None:
    messages = [
        {"role": "system", "content": "Return concise JSON."},
        {"role": "user", "content": 'Return {"ok": true}.'},
    ]
    _ = generate(
        tokenizer,
        model,
        messages,
        seed=1,
        max_input_tokens=128,
        max_new_tokens=16,
        temperature=0.0,
    )


def run(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset)
    validate_experiment_inputs(dataset_path, list(args.cases))
    if args.validate_only:
        print(
            json.dumps(
                {
                    "valid": True,
                    "dataset": str(dataset_path),
                    "cases": list(args.cases),
                    "skill_commit": PINNED_SKILL_COMMIT,
                    "skill_blob_sha": PINNED_SKILL_SHA,
                    "cost_reference_blob_sha": PINNED_COST_REFERENCE_SHA,
                },
                indent=2,
            )
        )
        return 0

    torch.set_num_threads(max(1, int(args.threads)))
    torch.set_num_interop_threads(1)
    random.seed(args.seed)

    dataset = load_dataset(dataset_path)
    case_index = {case.id: case for case in dataset.cases}
    missing = sorted(set(args.cases) - set(case_index))
    if missing:
        raise ValueError(f"Unknown cases: {missing}")
    selected_cases = [case_index[case_id] for case_id in args.cases]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(exist_ok=True)

    started_at = utc_now()
    tokenizer, model = load_model(args.model)
    warm_up(tokenizer, model)

    work: list[tuple[int, Case, Condition]] = []
    for repetition in range(1, args.repetitions + 1):
        paired = [
            (repetition, case, CONDITION_OBJECTS[condition])
            for case in selected_cases
            for condition in CONDITIONS
        ]
        random.Random(args.seed + repetition).shuffle(paired)
        work.extend(paired)

    records: list[JsonObject] = []
    for index, (repetition, case, condition) in enumerate(work, start=1):
        paired_seed = args.seed + repetition * 100 + list(args.cases).index(case.id)
        print(
            f"[{index}/{len(work)}] model={args.model} case={case.id} "
            f"condition={condition.name} repetition={repetition}",
            flush=True,
        )
        generation = generate(
            tokenizer,
            model,
            build_messages(case, condition),
            seed=paired_seed,
            max_input_tokens=args.max_input_tokens,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
        raw_path = output_dir / "raw" / (
            f"{case.id}--{condition.name}--trial-{repetition:02d}.txt"
        )
        raw_path.write_text(generation.text + "\n", encoding="utf-8")

        parse_error: str | None = None
        response: JsonObject | None = None
        try:
            compact = extract_json_object(generation.text)
            response = normalize_response(case, compact, generation, condition, args.model)
        except (ValueError, json.JSONDecodeError) as exc:
            parse_error = f"{type(exc).__name__}: {exc}"

        evaluation = evaluate_response(
            case,
            response,
            trial=repetition,
            execution_error=parse_error,
        )
        record: JsonObject = {
            "model": args.model,
            "condition": condition.name,
            "case_id": case.id,
            "trial": repetition,
            "seed": paired_seed,
            "skill_enabled": condition.use_skill,
            "pricing_tool_enabled": condition.use_pricing,
            "pricing_tool_mode": (
                "frozen-public-price-adapter" if condition.use_pricing else "disabled"
            ),
            "generation": {
                "duration_seconds": round(generation.duration_seconds, 6),
                "input_tokens": generation.input_tokens,
                "output_tokens": generation.output_tokens,
                "tokens_per_second": round(generation.tokens_per_second, 6),
            },
            "raw_output_path": str(raw_path.relative_to(output_dir)),
            "parse_error": parse_error,
            "response": response,
            "evaluation": evaluation,
        }
        records.append(record)
        dump_json(
            output_dir
            / "raw"
            / f"{case.id}--{condition.name}--trial-{repetition:02d}.json",
            record,
        )

    summaries = {
        condition: condition_summary(
            [record for record in records if record["condition"] == condition],
            args.repetitions,
        )
        for condition in CONDITIONS
    }
    completed_at = utc_now()
    result: JsonObject = {
        "schema_version": "1.0",
        "experiment": "aws-agent-skill-pricing-ablation",
        "model": args.model,
        "dataset": {"id": dataset.id, "version": dataset.version},
        "cases": list(args.cases),
        "conditions": list(CONDITIONS),
        "repetitions": args.repetitions,
        "generation": {
            "temperature": args.temperature,
            "max_input_tokens": args.max_input_tokens,
            "max_new_tokens": args.max_new_tokens,
            "threads": args.threads,
            "base_seed": args.seed,
        },
        "skill_provenance": {
            "repository": "awslabs/agent-plugins",
            "commit": PINNED_SKILL_COMMIT,
            "skill_blob_sha": PINNED_SKILL_SHA,
            "cost_reference_blob_sha": PINNED_COST_REFERENCE_SHA,
        },
        "pricing_tool": {
            "mode": "frozen-public-price-adapter",
            "live_aws_pricing_mcp": False,
            "reason": "Credential-free controlled ablation; no oracle totals/ranges exposed.",
        },
        "started_at": started_at,
        "completed_at": completed_at,
        "summaries": summaries,
        "trials": records,
    }
    dump_json(output_dir / "results.json", result)
    dump_json(output_dir / "summary.json", summaries)
    write_csv(output_dir / "summary.csv", summaries)
    (output_dir / "report.md").write_text(
        render_report(
            model_id=args.model,
            repetitions=args.repetitions,
            cases=list(args.cases),
            summaries=summaries,
            records=records,
            started_at=started_at,
            completed_at=completed_at,
        ),
        encoding="utf-8",
    )

    print(json.dumps(summaries, ensure_ascii=False, indent=2), flush=True)
    # This benchmark is diagnostic: model failures must not fail the workflow.
    # A nonzero exit is reserved for harness/runtime errors.
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="datasets/aws-cost-v1")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-input-tokens", type=int, default=8192)
    parser.add_argument("--max-new-tokens", type=int, default=420)
    parser.add_argument("--threads", type=int, default=max(1, os.cpu_count() or 2))
    parser.add_argument("--seed", type=int, default=20260726)
    parser.add_argument("--output-dir", default="artifacts/aws-agent-ablation")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")
    if args.temperature < 0:
        parser.error("--temperature must be >= 0")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
