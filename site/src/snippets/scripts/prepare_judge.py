import json
import random
import sys
import uuid
from pathlib import Path

run_dir = Path(sys.argv[1])
judge_dir = Path(sys.argv[2])
if judge_dir.exists():
    raise SystemExit(f"Output already exists: {judge_dir}; use a new directory")
trials = []
for verdict in sorted(run_dir.glob("trial-*/verdict.json")):
    if json.loads(verdict.read_text(encoding="utf-8"))["passed"]:
        trials.append(verdict.parent)
if not trials:
    raise SystemExit(f"No passing trials in {run_dir}; fix the cause before judging")
random.SystemRandom().shuffle(trials)
mapping = {}
for trial in trials:
    answer = json.loads((trial / "answer.json").read_text(encoding="utf-8"))
    answer.pop("case_id", None)
    answer.pop("agent_metrics", None)
    item_id = "item-" + uuid.uuid4().hex[:12]
    item_dir = judge_dir / item_id
    item_dir.mkdir(parents=True)
    payload = {"judge_item_id": item_id, "rubric_version": "judge-v1", "answer": answer}
    (item_dir / "judge-input.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    mapping[item_id] = str(trial)
(judge_dir / "mapping.json").write_text(
    json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"Prepared {len(mapping)} items in {judge_dir}")
