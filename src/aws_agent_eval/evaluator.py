from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .types import Case, JsonObject
from .utils import load_json


@dataclass(frozen=True)
class Check:
    code: str
    passed: bool
    critical: bool
    weight: float
    detail: str

    def as_dict(self) -> JsonObject:
        return {
            "code": self.code,
            "passed": self.passed,
            "critical": self.critical,
            "weight": self.weight,
            "detail": self.detail,
        }


def evaluate_response(
    case: Case,
    response: JsonObject | None,
    *,
    trial: int,
    execution_error: str | None = None,
    schema_path: Path | None = None,
) -> JsonObject:
    checks: list[Check] = []
    if execution_error is not None:
        checks.append(Check("execution_error", False, True, 15, execution_error))
    else:
        checks.append(Check("execution_ok", True, True, 15, "Agent command completed"))

    if response is None:
        checks.append(Check("response_missing", False, True, 85, "No response JSON available"))
        return _finalize(case.id, trial, checks)

    schema = schema_path or Path(__file__).resolve().parents[2] / "schemas/agent-output.schema.json"
    schema_errors = _schema_errors(response, schema)
    checks.append(
        Check(
            "schema_valid",
            not schema_errors,
            True,
            10,
            "valid" if not schema_errors else "; ".join(schema_errors),
        )
    )
    if schema_errors:
        return _finalize(case.id, trial, checks)

    expected = case.data["expected"]
    assert isinstance(expected, dict)
    status = str(response["status"])
    expected_status = str(expected["status"])
    checks.append(
        Check(
            "status_match",
            status == expected_status,
            True,
            15,
            f"expected={expected_status}, actual={status}",
        )
    )
    checks.append(
        Check(
            "case_identity",
            response["case_id"] == case.id
            and response["region"] == case.data["region"]
            and response["currency"] == case.data["currency"],
            True,
            5,
            "case_id, region, and currency must match the case",
        )
    )

    if expected_status == "completed":
        checks.extend(_completed_checks(expected, response))
    elif expected_status == "needs_clarification":
        checks.extend(_clarification_checks(expected, response))
    else:
        checks.append(Check("unsupported_status", status == "unsupported", True, 45, status))

    checks.extend(_quality_checks(expected, response))
    return _finalize(case.id, trial, checks)


def _schema_errors(response: JsonObject, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(response), key=lambda error: list(error.absolute_path))
    formatted: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        formatted.append(f"{location}: {error.message}")
    return formatted


def _completed_checks(expected: dict[str, Any], response: JsonObject) -> list[Check]:
    checks: list[Check] = []
    estimates = response["service_estimates"]
    assert isinstance(estimates, list)
    by_service: dict[str, dict[str, Any]] = {}
    for estimate in estimates:
        assert isinstance(estimate, dict)
        by_service[_normalise_service(str(estimate["service"]))] = estimate

    required_services = [str(value) for value in expected["required_services"]]
    missing = [
        service for service in required_services if _normalise_service(service) not in by_service
    ]
    checks.append(
        Check(
            "service_coverage",
            not missing,
            True,
            15,
            "all required services present" if not missing else f"missing={missing}",
        )
    )

    range_failures: list[str] = []
    for item in expected["service_ranges"]:
        assert isinstance(item, dict)
        service = str(item["service"])
        estimate = by_service.get(_normalise_service(service))
        if estimate is None:
            continue
        actual = float(estimate["monthly_cost_usd"])
        minimum = float(item["minimum"])
        maximum = float(item["maximum"])
        if not minimum <= actual <= maximum:
            range_failures.append(f"{service}={actual:.6f} not in [{minimum}, {maximum}]")
    checks.append(
        Check(
            "service_ranges",
            not range_failures,
            True,
            15,
            "within ranges" if not range_failures else "; ".join(range_failures),
        )
    )

    actual_total_value = response["monthly_total_usd"]
    total_range = expected["total_range"]
    total_ok = isinstance(actual_total_value, (int, float)) and isinstance(total_range, dict)
    total_detail = "monthly_total_usd is missing"
    if total_ok:
        actual_total = float(actual_total_value)
        minimum = float(total_range["minimum"])
        maximum = float(total_range["maximum"])
        total_ok = minimum <= actual_total <= maximum
        total_detail = f"actual={actual_total:.6f}, expected=[{minimum}, {maximum}]"
    checks.append(Check("total_range", total_ok, True, 10, total_detail))

    arithmetic_ok = False
    arithmetic_detail = "monthly_total_usd is missing"
    if isinstance(actual_total_value, (int, float)):
        actual_total = float(actual_total_value)
        calculated = sum(float(item["monthly_cost_usd"]) for item in estimates)
        tolerance = max(0.02, abs(actual_total) * 0.005)
        arithmetic_ok = math.isclose(actual_total, calculated, abs_tol=tolerance)
        arithmetic_detail = (
            f"reported={actual_total:.6f}, sum={calculated:.6f}, tolerance={tolerance:.6f}"
        )
    checks.append(Check("arithmetic_consistency", arithmetic_ok, True, 10, arithmetic_detail))

    required_source_urls = {str(value) for value in expected["required_source_urls"]}
    actual_source_urls = {
        str(source["url"])
        for estimate in estimates
        if isinstance(estimate, dict)
        for source in estimate.get("sources", [])
        if isinstance(source, dict) and "url" in source
    }
    missing_source_urls = sorted(required_source_urls - actual_source_urls)
    checks.append(
        Check(
            "required_source_urls",
            not missing_source_urls,
            True,
            5,
            "all required source URLs present"
            if not missing_source_urls
            else f"missing={missing_source_urls}",
        )
    )
    return checks


def _clarification_checks(expected: dict[str, Any], response: JsonObject) -> list[Check]:
    missing_inputs = response["missing_inputs"]
    assert isinstance(missing_inputs, list)
    actual_ids = {
        str(item["id"]) for item in missing_inputs if isinstance(item, dict) and "id" in item
    }
    required = {str(value) for value in expected["required_missing_input_ids"]}
    missing = sorted(required - actual_ids)
    monetary_empty = response["monthly_total_usd"] is None and not response["service_estimates"]
    return [
        Check(
            "missing_input_coverage",
            not missing,
            True,
            35,
            "all required questions present" if not missing else f"missing={missing}",
        ),
        Check(
            "no_fabricated_estimate",
            monetary_empty,
            True,
            20,
            "no estimate emitted" if monetary_empty else "monetary values were emitted",
        ),
    ]


def _quality_checks(expected: dict[str, Any], response: JsonObject) -> list[Check]:
    assumptions = response["assumptions"]
    assert isinstance(assumptions, list)
    actual_assumptions = {
        str(item["id"]) for item in assumptions if isinstance(item, dict) and "id" in item
    }
    required_assumptions = {str(value) for value in expected["required_assumption_ids"]}
    missing_assumptions = sorted(required_assumptions - actual_assumptions)

    estimates = response["service_estimates"]
    assert isinstance(estimates, list)
    sources_ok = all(
        isinstance(item, dict)
        and isinstance(item.get("sources"), list)
        and len(item["sources"]) > 0
        for item in estimates
    )
    if not estimates and response["status"] == "needs_clarification":
        sources_ok = True

    return [
        Check(
            "assumption_coverage",
            not missing_assumptions,
            False,
            5,
            "complete" if not missing_assumptions else f"missing={missing_assumptions}",
        ),
        Check(
            "source_coverage",
            sources_ok,
            False,
            5,
            "each service has a source" if sources_ok else "one or more services lack sources",
        ),
    ]


def _finalize(case_id: str, trial: int, checks: list[Check]) -> JsonObject:
    total_weight = sum(check.weight for check in checks)
    earned = sum(check.weight for check in checks if check.passed)
    score = 0.0 if total_weight == 0 else round(100 * earned / total_weight, 2)
    critical_failures = [check.code for check in checks if check.critical and not check.passed]
    return {
        "case_id": case_id,
        "trial": trial,
        "passed": not critical_failures,
        "score": score,
        "critical_failures": critical_failures,
        "checks": [check.as_dict() for check in checks],
    }


def _normalise_service(value: str) -> str:
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
        "mq": "amazon mq",
        "app runner": "aws app runner",
        "api gateway websocket": "amazon api gateway websocket",
        "amazon api gateway websocket api": "amazon api gateway websocket",
        "cloudwatch logs": "amazon cloudwatch logs",
        "cloudwatch": "amazon cloudwatch",
        "aws cloudwatch": "amazon cloudwatch",
        "cloudwatch metrics": "amazon cloudwatch",
        "amazon cloudwatch metrics": "amazon cloudwatch",
        "cloudwatch custom metrics": "amazon cloudwatch",
        "amazon cloudwatch custom metrics": "amazon cloudwatch",
        "kms": "aws kms",
        "aws key management service": "aws kms",
        "amazon key management service": "aws kms",
        "kinesis": "amazon kinesis",
        "amazon kinesis data streams": "amazon kinesis",
        "kinesis data streams": "amazon kinesis",
        "amazon kinesis data firehose": "amazon data firehose",
        "aws data firehose": "amazon data firehose",
        "kinesis data firehose": "amazon data firehose",
        "vpc": "amazon vpc",
        "aws vpc": "amazon vpc",
        "security hub": "aws security hub",
        "amazon security hub": "aws security hub",
        "guardduty": "amazon guardduty",
        "aws guardduty": "amazon guardduty",
        "route 53": "amazon route 53",
        "aws route 53": "amazon route 53",
        "macie": "amazon macie",
        "aws macie": "amazon macie",
        "secrets manager": "aws secrets manager",
        "amazon secrets manager": "aws secrets manager",
        "codepipeline": "aws codepipeline",
        "amazon codepipeline": "aws codepipeline",
        "codebuild": "aws codebuild",
        "amazon codebuild": "aws codebuild",
        "systems manager": "aws systems manager",
        "amazon systems manager": "aws systems manager",
        "waf": "aws waf",
        "amazon waf": "aws waf",
        "cognito": "amazon cognito",
        "aws cognito": "amazon cognito",
        "athena": "amazon athena",
        "aws athena": "amazon athena",
        "glue": "aws glue",
        "amazon glue": "aws glue",
        "cloudtrail": "aws cloudtrail",
        "amazon cloudtrail": "aws cloudtrail",
        "config": "aws config",
        "amazon config": "aws config",
    }
    normalised = " ".join(value.casefold().replace("_", " ").replace("-", " ").split())
    return aliases.get(normalised, normalised)
