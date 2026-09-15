import json
import math
import sys
from pathlib import Path

verdicts = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(Path(sys.argv[1]).glob("trial-*/verdict.json"))
]
n = len(verdicts)
if n != 5:
    raise SystemExit(f"Expected 5 verdicts, found {n}: {sys.argv[1]}")
successes = sum(item["passed"] for item in verdicts)
p = successes / n
z = 1.96
denominator = 1 + z * z / n
center = (p + z * z / (2 * n)) / denominator
margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator

summary = {
    "trials": n,
    "successes": successes,
    "success_rate": p,
    "wilson_95ci": [max(0, center - margin), min(1, center + margin)],
    "pass_at_k": successes > 0,
    "pass_power_k": successes == n,
}
print(json.dumps(summary, indent=2))
