"""Exercise the handout's actual shell blocks with offline CLI stand-ins."""

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "site/src/content/docs"
SNIPPETS = ROOT / "site/src/snippets"


def blocks(chapter: str) -> list[str]:
    source = next(DOCS.glob(f"{chapter}-*.mdx")).read_text()
    return [textwrap.dedent(body) for body in re.findall(r"```bash\n(.*?)```", source, re.S)]


def run(command: str, cwd: Path, stdin: str = "") -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PATH=f"{cwd / 'bin'}:{Path(sys.executable).parent}:{os.environ['PATH']}")
    return subprocess.run(
        ["bash", "-c", command], cwd=cwd, env=env, input=stdin,
        text=True, capture_output=True, timeout=30, check=False,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    manual = tmp_path / "workshop/manual"
    shutil.copytree(SNIPPETS, manual)
    shutil.copytree(ROOT / "schemas", manual / "schemas")
    for case in ("cfn-missing-usage", "cfn-static-site"):
        shutil.copytree(ROOT / f"datasets/aws-cost-v1/cases/{case}/input", manual / "cases" / case / "input")
    (manual / "config/pricing-mcp.json").write_text('{"mcpServers":{}}')
    shutil.copyfile(manual / "experiment.json", manual / "experiment-pricing-mcp.json")
    return tmp_path


def answer(case: str = "cfn-missing-usage") -> dict:
    oracle = json.loads((SNIPPETS / f"cases/{case}/oracle.json").read_text())
    result = {
        "schema_version": "1.0", "case_id": case, "status": oracle["expected_status"],
        "region": "us-east-1", "currency": "USD", "price_effective_at": None,
        "monthly_total_usd": None, "service_estimates": [], "assumptions": [],
        "excluded_costs": [], "missing_inputs": [
            {"id": name, "question": "Please specify usage"}
            for name in oracle.get("required_missing_input_ids", [])
        ], "confidence": 0.5, "summary": "Offline fixture",
    }
    if case == "cfn-static-site":
        result["monthly_total_usd"] = 198.88
        result["service_estimates"] = [
            {"service": service, "resource_ids": [], "monthly_cost_usd": cost,
             "formula": "Offline fixture", "pricing_dimensions": [], "sources": [
                 {"title": service, "url": url, "retrieved_at": "2026-07-25T00:00:00Z"}
             ]}
            for service, cost, url in zip(
                oracle["required_services"], [4.8, 194.08], oracle["required_source_urls"], strict=True
            )
        ]
    return result


def install_fake_cli(workspace: Path) -> None:
    bindir = workspace / "bin"
    bindir.mkdir()
    # Fixtures live outside agent inputs. The fake CLI only verifies command plumbing.
    for case in ("cfn-missing-usage", "cfn-static-site"):
        (bindir / f"{case}.json").write_text(json.dumps(answer(case)))
    script = '''#!/usr/bin/env python
import json, sys
from pathlib import Path
args = sys.argv[1:]
if Path("judge-input.json").exists():
    item = json.loads(Path("judge-input.json").read_text())
    result = {"judge_item_id": item["judge_item_id"], "repeat": int(Path("repeat.txt").read_text()),
      "scores": {k: 4 for k in ["assumption_clarity", "uncertainty_handling", "exclusion_clarity", "actionability"]},
      "semantic_pass": True, "critical_concern": None, "rationale": "Offline test"}
else:
    case = json.loads(Path("case-public.json").read_text())
    assert Path(case["input_files"][0]).is_file()
    assert not Path("oracle.json").exists()
    result = json.loads((Path(__file__).parent / (case["id"] + ".json")).read_text())
if Path(sys.argv[0]).name == "claude":
    assert "--output-format" in args and "--strict-mcp-config" in args
    config = args[args.index("--mcp-config") + 1]
    json.loads(config if config.startswith("{") else Path(config).read_text())
    print(json.dumps({"is_error": False, "structured_output": result}))
else:
    output = args[args.index("--output-last-message") + 1]
    Path(output).write_text(json.dumps(result))
    print('{"type":"offline_event"}')
'''
    for name in ("codex", "claude"):
        p = bindir / name
        p.write_text(script)
        p.chmod(0o755)


@pytest.mark.parametrize("cli_index", [0, 1], ids=["codex", "claude"])
def test_copy_paste_repeat_and_judge_pipeline(workspace: Path, cli_index: int) -> None:
    install_fake_cli(workspace)
    loops = [b for b in blocks("06") if "for number in" in b]
    for command in (loops[cli_index], loops[cli_index + 2]):
        result = run(command, workspace)
        assert result.returncode == 0, result.stderr
    manual = workspace / "workshop/manual"
    verdicts = list(manual.glob("runs/*-batch-01/*/trial-*/verdict.json"))
    assert len(verdicts) == 10
    assert all(json.loads(p.read_text())["passed"] for p in verdicts)
    before = {p: p.stat().st_mtime_ns for p in verdicts}
    assert run(loops[cli_index], workspace).returncode == 0
    assert before == {p: p.stat().st_mtime_ns for p in verdicts}
    for command in [b for b in blocks("06") if b.startswith("python workshop/manual/scripts/summarize.py")]:
        assert run(command, workspace).returncode == 0
    prepare = next(b for b in blocks("07") if b.startswith("python workshop/manual/scripts/prepare_judge.py"))
    assert run(prepare, workspace).returncode == 0
    items = list(manual.glob("runs/judge-batch-01/item-*/judge-input.json"))
    assert len(items) == 5
    assert all("case_id" not in json.loads(p.read_text())["answer"] for p in items)
    judge = [b for b in blocks("07") if "for repeat in" in b][cli_index]
    result = run(judge, workspace, "offline-model\n")
    assert result.returncode == 0, result.stderr
    aggregate = next(b for b in blocks("07") if "scripts/aggregate_judge.py" in b)
    result = run(aggregate, workspace)
    assert result.returncode == 0, result.stderr
    assert len(list(manual.glob("runs/judge-batch-01/item-*/summary.json"))) == 5


@pytest.mark.parametrize("failure", [None, "schema", "status", "clarification", "invented", "total", "service", "source", "arithmetic"])
def test_checker_accepts_valid_and_rejects_invalid(workspace: Path, failure: str | None) -> None:
    case = "cfn-static-site" if failure in {"total", "service", "source", "arithmetic"} else "cfn-missing-usage"
    result = answer(case)
    if failure == "schema":
        del result["confidence"]
    elif failure == "status":
        result["status"] = "error"
    elif failure == "clarification":
        result["missing_inputs"] = []
    elif failure == "invented":
        result["monthly_total_usd"] = 12
    elif failure == "total":
        result["monthly_total_usd"] = 999
    elif failure == "service":
        result["service_estimates"] = []
    elif failure == "source":
        result["service_estimates"][0]["sources"] = []
    elif failure == "arithmetic":
        result["service_estimates"][0]["monthly_cost_usd"] = 0
    (workspace / "answer.json").write_text(json.dumps(result))
    process = run(f"python workshop/manual/scripts/check_result.py answer.json workshop/manual/cases/{case}/oracle.json", workspace)
    assert json.loads(process.stdout)["passed"] is (failure is None)
    assert process.returncode == (0 if failure is None else 1)


def test_malformed_answer_and_empty_summary_fail(workspace: Path) -> None:
    (workspace / "broken.json").write_text("not json")
    result = run("python workshop/manual/scripts/check_result.py broken.json workshop/manual/cases/cfn-missing-usage/oracle.json", workspace)
    assert result.returncode == 1 and not json.loads(result.stdout)["passed"]
    assert run("python workshop/manual/scripts/summarize.py empty", workspace).returncode != 0
    assert run("python workshop/manual/scripts/aggregate_judge.py empty", workspace).returncode != 0


@pytest.mark.parametrize("problem", [None, "concern", "score", "duplicate"])
def test_judge_does_not_hide_critical_or_incomplete_results(workspace: Path, problem: str | None) -> None:
    item = workspace / "item"
    for number in (1, 2, 3):
        folder = item / f"repeat-{number}"
        folder.mkdir(parents=True)
        result = {
            "judge_item_id": "anonymous", "repeat": 1 if problem == "duplicate" else number,
            "scores": {name: 2 if problem == "score" else 4 for name in (
                "assumption_clarity", "uncertainty_handling", "exclusion_clarity", "actionability"
            )}, "semantic_pass": True,
            "critical_concern": "unresolved" if problem == "concern" and number == 1 else None,
            "rationale": "Fixture",
        }
        (folder / "judgment.json").write_text(json.dumps(result))
    process = run("python workshop/manual/scripts/aggregate_judge.py item", workspace)
    if problem == "duplicate":
        assert process.returncode != 0
    else:
        assert json.loads(process.stdout)["semantic_pass"] is (problem is None)


def test_claude_error_is_not_saved_as_answer(workspace: Path) -> None:
    (workspace / "raw.json").write_text('{"is_error":true,"structured_output":{"status":"completed"}}')
    result = run("python workshop/manual/scripts/extract_claude.py raw.json answer.json", workspace)
    assert result.returncode != 0
    assert not (workspace / "answer.json").exists()


def test_all_shell_examples_are_syntactically_valid() -> None:
    for path in DOCS.rglob("*.mdx"):
        for body in re.findall(r"```bash\n(.*?)```", path.read_text(), re.S):
            result = subprocess.run(["bash", "-n"], input=textwrap.dedent(body), text=True, capture_output=True)
            assert result.returncode == 0, f"{path}: {result.stderr}"
