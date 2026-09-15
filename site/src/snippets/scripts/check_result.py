import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

try:
    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    oracle = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    schema_path = Path(__file__).resolve().parents[1] / "schemas/agent-output.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
except Exception as error:
    print(json.dumps({"passed": False, "errors": [f"JSON/schema/input: {error}"]}))
    raise SystemExit(1) from error

errors: list[str] = []

if result.get("status") != oracle["expected_status"]:
    errors.append("status mismatch")

if oracle["expected_status"] == "needs_clarification":
    if result["monthly_total_usd"] is not None or result["service_estimates"]:
        errors.append("clarification must not invent an estimate")

required_services = set(oracle.get("required_services", []))
actual_services = {
    item.get("service") for item in result.get("service_estimates", [])
}
if not required_services <= actual_services:
    errors.append("required service missing")

required_missing = set(oracle.get("required_missing_input_ids", []))
actual_missing = {item.get("id") for item in result.get("missing_inputs", [])}
if not required_missing <= actual_missing:
    errors.append("required clarification missing")

expected_total = oracle.get("monthly_total_usd")
if expected_total:
    total = result.get("monthly_total_usd")
    if not isinstance(total, (int, float)):
        errors.append("monthly total missing")
    elif not expected_total["minimum"] <= total <= expected_total["maximum"]:
        errors.append("monthly total outside oracle range")

    subtotal = sum(
        item.get("monthly_cost_usd", 0)
        for item in result.get("service_estimates", [])
    )
    if isinstance(total, (int, float)) and abs(total - subtotal) > 0.02:
        errors.append("service subtotal mismatch")

required_urls = set(oracle.get("required_source_urls", []))
actual_urls = {
    source.get("url")
    for item in result.get("service_estimates", [])
    for source in item.get("sources", [])
}
if not required_urls <= actual_urls:
    errors.append("required source missing")

print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
raise SystemExit(1 if errors else 0)
