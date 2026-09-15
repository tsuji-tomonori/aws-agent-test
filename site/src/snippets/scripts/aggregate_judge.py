import json
import sys
from pathlib import Path
from statistics import median

from jsonschema import Draft202012Validator

items = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(Path(sys.argv[1]).glob("repeat-*/judgment.json"))
]
if len(items) != 3 or {item.get("repeat") for item in items} != {1, 2, 3}:
    raise SystemExit("Exactly 3 judgments with repeats 1, 2, 3 are required")
schema_path = Path(__file__).resolve().parents[1] / "schemas/judge-output.schema.json"
validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
for item in items:
    validator.validate(item)
if len({item["judge_item_id"] for item in items}) != 1:
    raise SystemExit("Judgments must refer to the same anonymous item")
dimensions = [
    "assumption_clarity",
    "uncertainty_handling",
    "exclusion_clarity",
    "actionability",
]
concerns = [item["critical_concern"] for item in items if item["critical_concern"]]
result = {
    "repeats": len(items),
    "median_scores": {
        name: median(item["scores"][name] for item in items)
        for name in dimensions
    },
    "semantic_pass": sum(
        item["semantic_pass"] and min(item["scores"].values()) >= 3
        and not item["critical_concern"]
        for item in items
    ) >= 2 and not concerns,
    "critical_concerns": concerns,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
