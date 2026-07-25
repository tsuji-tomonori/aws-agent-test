import json
from pathlib import Path

from aws_agent_eval.dataset import load_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_loads_all_cases() -> None:
    dataset = load_dataset(ROOT / "datasets/aws-cost-v1")
    assert dataset.id == "aws-cost-v1"
    assert dataset.version == "1.1.0"
    assert {case.id for case in dataset.cases} == {
        "cfn-serverless-api",
        "cfn-static-site",
        "cdk-fargate-alb",
        "cfn-missing-usage",
        "aws-official-priority-messaging-medium",
    }


def test_official_reference_preserves_aws_cost_table_and_provenance() -> None:
    path = (
        ROOT
        / "datasets/aws-cost-v1/cases/aws-official-priority-messaging-medium"
        / "provenance/official-reference.json"
    )
    reference = json.loads(path.read_text(encoding="utf-8"))
    assert reference["publisher"] == "Amazon Web Services"
    assert reference["diagram"]["sample_repository_commit"] == (
        "6cab865650b4080ade6aa39b8e66372074cc597f"
    )
    table = reference["published_cost_table_usd_per_month"]
    assert table["medium"]["services"]["AWS App Runner"] == {
        "minimum": 50,
        "maximum": 150,
    }
    assert table["medium"]["total"] == {"minimum": 135, "maximum": 295}
    assert table["large"]["total"] == {"minimum": 850, "maximum": 1570}
    small_max_sum = sum(
        service["maximum"] for service in table["small"]["services"].values()
    )
    assert small_max_sum == 85
    assert table["small"]["total"]["maximum"] == 95


def test_aws_official_solutions_dataset_uses_hidden_published_oracles() -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    assert dataset.id == "aws-official-solutions-v1"
    assert dataset.version == "1.0.0"
    assert {case.id for case in dataset.cases} == {
        "official-instance-scheduler-small",
        "official-cloud-migration-factory-default",
        "official-landing-zone-accelerator-sandbox",
    }

    expected_totals = {
        "official-instance-scheduler-small": 9.15,
        "official-cloud-migration-factory-default": 14.31,
        "official-landing-zone-accelerator-sandbox": 430.22,
    }
    for case in dataset.cases:
        reference = case.data["official_reference"]
        assert reference["publisher"] == "Amazon Web Services"
        assert reference["credentials_required"] is False
        assert case.data["oracle"]["monthly_total_usd"] == expected_totals[case.id]
        cost_url = reference["cost_page_url"]
        exposed_urls = {
            value
            for asset in case.data["public_assets"]
            for value in (asset["url"], asset["source_page_url"])
        }
        assert cost_url not in exposed_urls
        assert {asset["role"] for asset in case.data["public_assets"]} == {
            "architecture-diagram",
            "cloudformation-template",
        }
        assert all(asset["authentication"] == "none" for asset in case.data["public_assets"])
