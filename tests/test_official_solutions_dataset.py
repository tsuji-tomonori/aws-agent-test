from pathlib import Path

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.prompt import render_agent_prompt


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets/aws-official-solutions-v1"


def test_official_solutions_dataset_contains_aws_published_examples() -> None:
    dataset = load_dataset(DATASET_DIR)
    assert dataset.id == "aws-official-solutions-v1"
    assert dataset.version == "1.0.0"

    cases = {case.id: case for case in dataset.cases}
    assert set(cases) == {
        "official-instance-scheduler-small",
        "official-cloud-migration-factory-default",
        "official-landing-zone-accelerator-sandbox",
    }
    assert cases["official-instance-scheduler-small"].data["oracle"][
        "monthly_total_usd"
    ] == 9.15
    assert cases["official-cloud-migration-factory-default"].data["oracle"][
        "monthly_total_usd"
    ] == 14.31
    assert cases["official-landing-zone-accelerator-sandbox"].data["oracle"][
        "monthly_total_usd"
    ] == 430.22

    for case in dataset.cases:
        reference = case.data["official_reference"]
        assert reference["publisher"] == "Amazon Web Services"
        assert reference["credentials_required"] is False
        assert case.data["expected"]["required_source_urls"] == [
            reference["cost_page_url"]
        ]
        assets = case.data["public_assets"]
        assert {item["role"] for item in assets} >= {
            "architecture-diagram",
            "cloudformation-template",
        }
        assert all(item["authentication"] == "none" for item in assets)


def test_official_prompt_exposes_assets_but_not_hidden_oracle() -> None:
    dataset = load_dataset(DATASET_DIR)
    case = next(
        item for item in dataset.cases if item.id == "official-instance-scheduler-small"
    )
    rendered = render_agent_prompt(
        case,
        ROOT / "prompts/agent-cost-estimation.md",
    )

    for asset in case.data["public_assets"]:
        assert asset["url"] in rendered
        assert asset["source_page_url"] in rendered
    assert case.data["official_reference"]["cost_page_url"] not in rendered
    assert str(case.data["oracle"]["monthly_total_usd"]) not in rendered
    assert "{{PUBLIC_ASSETS}}" not in rendered
