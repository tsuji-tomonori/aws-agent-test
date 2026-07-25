from pathlib import Path

from aws_agent_eval.assets import public_asset_prompt_items
from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.prompt import render_agent_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_official_reference_prompt_contains_assets_but_not_cost_or_oracle() -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    case = next(item for item in dataset.cases if item.id == "official-instance-scheduler-small")
    prompt = render_agent_prompt(
        case,
        ROOT / "prompts/agent-cost-estimation.md",
        public_asset_prompt_items(case),
    )

    reference = case.data["official_reference"]
    assert case.data["public_assets"][0]["url"] in prompt
    assert case.data["public_assets"][1]["url"] in prompt
    assert reference["cost_page_url"] not in prompt
    assert '"monthly_total_usd": 9.15' not in prompt
    assert "~$9.15" not in prompt
