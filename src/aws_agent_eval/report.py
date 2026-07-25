from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import dump_json, load_json


def generate_report(run_dir: Path) -> Path:
    results = load_json(run_dir / "results.json")
    summary = results["summary"]
    trials = results["trials"]
    assert isinstance(summary, dict)
    assert isinstance(trials, list)

    lines = [
        "# AI Agent evaluation report",
        "",
        "## Run identity",
        "",
        f"- Dataset: `{results['dataset']['id']}` `{results['dataset']['version']}`",
        f"- Profile: `{results['profile']['name']}`",
        f"- Repetitions: `{results['repetitions']}`",
        f"- Started: `{results['started_at']}`",
        f"- Completed: `{results['completed_at']}`",
        "",
        "## Reliability summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Trials | {summary['trials']} |",
        f"| Successes | {summary['successes']} |",
        f"| Success rate | {_percent(summary['success_rate'])} |",
        f"| Wilson 95% CI | {_percent(summary['wilson_95']['lower'])} – {_percent(summary['wilson_95']['upper'])} |",
        f"| pass@{summary['repetitions']} | {_percent(summary['pass_at_k'])} |",
        f"| pass^{summary['repetitions']} | {_percent(summary['pass_power_k'])} |",
        f"| Average score | {summary['average_score']:.3f} |",
        f"| Average latency | {summary['average_latency_seconds']:.3f}s |",
        "",
        "> `pass@k` means at least one success per case. `pass^k` means every repeated trial succeeded.",
        "",
        "## Trial results",
        "",
        "| Case | Trial | Pass | Score | Latency | Critical failures |",
        "|---|---:|:---:|---:|---:|---|",
    ]
    for item in trials:
        assert isinstance(item, dict)
        evaluation = item["evaluation"]
        execution = item["execution"]
        failures = ", ".join(evaluation["critical_failures"]) or "—"
        lines.append(
            f"| `{item['case_id']}` | {item['trial']} | "
            f"{'✅' if evaluation['passed'] else '❌'} | {evaluation['score']:.2f} | "
            f"{execution['duration_seconds']:.3f}s | {failures} |"
        )

    lines.extend(["", "## Failure taxonomy", ""])
    failure_counts = summary["failure_counts"]
    if failure_counts:
        lines.extend(["| Failure | Count |", "|---|---:|"])
        for code, count in failure_counts.items():
            lines.append(f"| `{code}` | {count} |")
    else:
        lines.append("No critical failures.")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report demonstrates behavior only for the recorded dataset/profile/repetition combination. "
            "It is not approval to deploy generated infrastructure. LLM Judge results, when present, may add "
            "semantic diagnostics but cannot override deterministic critical failures.",
            "",
        ]
    )
    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    dump_json(run_dir / "summary.json", summary)
    return report_path


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"
