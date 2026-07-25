from aws_agent_eval.statistics import summarise_trials, wilson_interval


def _trial(case_id: str, passed: bool) -> dict:
    return {
        "case_id": case_id,
        "execution": {"duration_seconds": 1.0},
        "response": None,
        "evaluation": {
            "passed": passed,
            "score": 100.0 if passed else 50.0,
            "critical_failures": [] if passed else ["example"],
        },
    }


def test_wilson_interval_is_bounded() -> None:
    lower, upper = wilson_interval(3, 3)
    assert 0 < lower < upper <= 1


def test_pass_at_k_and_pass_power_k_differ_for_flaky_cases() -> None:
    trials = [
        _trial("a", True),
        _trial("a", True),
        _trial("a", False),
        _trial("b", True),
        _trial("b", True),
        _trial("b", True),
    ]
    summary = summarise_trials(trials, repetitions=3)
    assert summary["pass_at_k"] == 1.0
    assert summary["pass_power_k"] == 0.5
