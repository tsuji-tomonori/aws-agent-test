import json
import sys
from pathlib import Path

raw_path, answer_path = map(Path, sys.argv[1:3])
raw = json.loads(raw_path.read_text(encoding="utf-8"))
answer = raw.get("structured_output")
if raw.get("is_error") or not isinstance(answer, dict):
    raise SystemExit(f"No successful structured_output in {raw_path}; inspect the raw result")
answer_path.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
