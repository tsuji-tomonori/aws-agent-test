from pathlib import Path

from aws_agent_eval.dataset import load_dataset
from aws_agent_eval.runner import load_profile, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_mock_experiment_is_reproducibly_green(tmp_path: Path) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-cost-v1")
    profile = load_profile(ROOT / "config/profiles/mock.json")
    result = run_experiment(dataset, profile, tmp_path / "run", repetitions=2)
    assert result["summary"]["trials"] == 10
    assert result["summary"]["success_rate"] == 1.0
    assert result["summary"]["pass_power_k"] == 1.0
    workspace = tmp_path / "run/workspaces/cfn-serverless-api/trial-01"
    assert not (workspace / "case.json").exists()
    assert (workspace / "input/template.yaml").exists()
    official_workspace = tmp_path / "run/workspaces/aws-official-priority-messaging-medium/trial-01"
    assert (official_workspace / "input/official-reference.md").exists()
    assert not (official_workspace / "provenance/official-reference.json").exists()


def test_flaky_profile_detects_repeat_failure(tmp_path: Path) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-cost-v1")
    profile = load_profile(ROOT / "config/profiles/mock-flaky.json")
    result = run_experiment(dataset, profile, tmp_path / "run", repetitions=3)
    assert result["summary"]["pass_at_k"] == 1.0
    assert result["summary"]["pass_power_k"] == 0.0
