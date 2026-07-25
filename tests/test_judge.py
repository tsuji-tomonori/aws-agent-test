import json
from pathlib import Path

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.judge import aggregate_judgments, prepare_judge_batch
from aws_agent_eval.runner import load_profile, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_judge_batch_is_anonymous_and_aggregates(tmp_path: Path) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-cost-v1")
    profile = load_profile(ROOT / "config/profiles/mock.json")
    run_dir = tmp_path / "run"
    run_experiment(
        dataset, profile, run_dir, repetitions=1, selected_case_ids={"cfn-serverless-api"}
    )
    batch = prepare_judge_batch(run_dir, repeats=3)
    lines = [json.loads(line) for line in batch.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3
    assert "profile" not in json.dumps(lines)

    judgments = run_dir / "judge/judgments.jsonl"
    with judgments.open("w", encoding="utf-8") as stream:
        for item in lines:
            stream.write(
                json.dumps(
                    {
                        "judge_item_id": item["judge_item_id"],
                        "repeat": item["repeat"],
                        "scores": {
                            "assumption_clarity": 4,
                            "uncertainty_handling": 4,
                            "exclusion_clarity": 3,
                            "actionability": 4,
                        },
                        "semantic_pass": True,
                        "critical_concern": None,
                        "rationale": "Clear and reproducible.",
                    }
                )
                + "\n"
            )
    output = aggregate_judgments(run_dir, judgments)
    aggregate = json.loads(output.read_text(encoding="utf-8"))
    assert aggregate["items"][0]["semantic_pass_majority"] is True
    assert aggregate["items"][0]["median_scores"]["exclusion_clarity"] == 3.0
