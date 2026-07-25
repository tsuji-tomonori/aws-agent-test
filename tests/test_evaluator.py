from pathlib import Path

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.evaluator import evaluate_response
from aws_agent_eval.mock_agent import build_response

ROOT = Path(__file__).resolve().parents[1]


def _case(case_id: str):
    dataset = load_dataset(ROOT / "datasets/aws-cost-v1")
    return next(case for case in dataset.cases if case.id == case_id)


def test_good_completed_response_passes() -> None:
    case = _case("cfn-serverless-api")
    response = build_response(case.data, mode="good", trial=1)
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is True
    assert result["critical_failures"] == []


def test_missing_service_is_critical() -> None:
    case = _case("cfn-serverless-api")
    response = build_response(case.data, mode="good", trial=1)
    response["service_estimates"] = response["service_estimates"][:-1]
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is False
    assert "service_coverage" in result["critical_failures"]


def test_fabricated_estimate_fails_clarification_case() -> None:
    case = _case("cfn-missing-usage")
    response = build_response(case.data, mode="good", trial=1)
    response["monthly_total_usd"] = 12.34
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is False
    assert "no_fabricated_estimate" in result["critical_failures"]


def test_schema_failure_is_critical() -> None:
    case = _case("cfn-serverless-api")
    response = build_response(case.data, mode="good", trial=1)
    del response["summary"]
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is False
    assert result["critical_failures"] == ["schema_valid"]


def test_official_reference_case_passes_with_published_midpoints() -> None:
    case = _case("aws-official-priority-messaging-medium")
    response = build_response(case.data, mode="good", trial=1)
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is True


def test_missing_required_primary_source_is_critical() -> None:
    case = _case("aws-official-priority-messaging-medium")
    response = build_response(case.data, mode="good", trial=1)
    for estimate in response["service_estimates"]:
        estimate["sources"][0]["url"] = "https://example.com/not-the-aws-source"
    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is False
    assert "required_source_urls" in result["critical_failures"]


def test_official_service_aliases_do_not_create_false_coverage_failures() -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    case = next(item for item in dataset.cases if item.id == "official-instance-scheduler-small")
    response = build_response(case.data, mode="good", trial=1)
    aliases = {
        "AWS Lambda": "Amazon Lambda",
        "AWS KMS": "AWS Key Management Service",
        "Amazon CloudWatch": "CloudWatch Metrics",
        "Amazon DynamoDB": "DynamoDB",
    }
    for estimate in response["service_estimates"]:
        estimate["service"] = aliases[estimate["service"]]

    result = evaluate_response(case, response, trial=1)
    assert result["passed"] is True
