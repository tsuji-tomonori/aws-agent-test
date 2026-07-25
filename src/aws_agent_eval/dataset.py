from __future__ import annotations

from pathlib import Path

from .assets import validate_case_public_assets
from .schema import validate_object
from .types import Case, Dataset
from .utils import load_json, safe_relative


def default_schema_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas"


def load_dataset(dataset_dir: Path, schema_dir: Path | None = None) -> Dataset:
    dataset_dir = dataset_dir.resolve()
    schemas = (schema_dir or default_schema_dir()).resolve()
    dataset_file = dataset_dir / "dataset.json"
    data = load_json(dataset_file)
    validate_object(data, schemas / "dataset.schema.json", label=str(dataset_file))

    seen: set[str] = set()
    cases: list[Case] = []
    for case_ref in data["cases"]:
        relative = safe_relative(str(case_ref))
        case_file = (dataset_dir / relative).resolve()
        if not case_file.is_relative_to(dataset_dir):
            raise ValueError(f"Case escapes dataset root: {case_ref}")
        case_data = load_json(case_file)
        validate_object(case_data, schemas / "case.schema.json", label=str(case_file))
        case_id = str(case_data["id"])
        if case_id in seen:
            raise ValueError(f"Duplicate case id: {case_id}")
        seen.add(case_id)
        _validate_case_files(case_file.parent, case_data)
        _validate_expected(case_id, case_data)
        _validate_oracle(case_id, case_data)
        validate_case_public_assets(case_id, case_data)
        cases.append(Case(path=case_file, data=case_data))
    return Dataset(root=dataset_dir, data=data, cases=tuple(cases))


def _validate_case_files(case_dir: Path, case_data: dict[str, object]) -> None:
    inputs = case_data["inputs"]
    if not isinstance(inputs, list):
        raise ValueError("Case inputs must be a list")
    references: list[object] = list(inputs)
    provenance = case_data.get("provenance_files", [])
    if isinstance(provenance, list):
        references.extend(provenance)
    for file_ref in references:
        relative = safe_relative(str(file_ref))
        path = (case_dir / relative).resolve()
        if not path.is_relative_to(case_dir.resolve()):
            raise ValueError(f"Case file escapes case root: {file_ref}")
        if not path.is_file():
            raise ValueError(f"Missing case file: {path}")


def _validate_expected(case_id: str, case_data: dict[str, object]) -> None:
    expected = case_data["expected"]
    assert isinstance(expected, dict)
    ranges = expected["service_ranges"]
    assert isinstance(ranges, list)
    for item in ranges:
        assert isinstance(item, dict)
        if float(item["minimum"]) > float(item["maximum"]):
            raise ValueError(f"{case_id}: service range minimum exceeds maximum")
    total_range = expected["total_range"]
    if isinstance(total_range, dict) and float(total_range["minimum"]) > float(
        total_range["maximum"]
    ):
        raise ValueError(f"{case_id}: total range minimum exceeds maximum")
    status = expected["status"]
    if status == "completed" and total_range is None:
        raise ValueError(f"{case_id}: completed case requires total_range")
    if status != "completed" and total_range is not None:
        raise ValueError(f"{case_id}: non-completed case must not define total_range")


def _validate_oracle(case_id: str, case_data: dict[str, object]) -> None:
    oracle = case_data["oracle"]
    assert isinstance(oracle, dict)
    calculations = oracle["service_calculations"]
    assert isinstance(calculations, list)
    expected = case_data["expected"]
    assert isinstance(expected, dict)
    total = oracle["monthly_total_usd"]
    if expected["status"] == "completed":
        if not isinstance(total, (int, float)):
            raise ValueError(f"{case_id}: completed case requires oracle monthly_total_usd")
        calculated = sum(float(item["monthly_cost_usd"]) for item in calculations)
        if abs(float(total) - calculated) > 0.01:
            raise ValueError(
                f"{case_id}: oracle total {total} does not match service sum {calculated}"
            )
        service_names = {str(item["service"]) for item in calculations}
        required = {str(item) for item in expected["required_services"]}
        if service_names != required:
            raise ValueError(
                f"{case_id}: oracle services {sorted(service_names)} != required {sorted(required)}"
            )
    elif total is not None or calculations:
        raise ValueError(f"{case_id}: non-completed case must have an empty oracle")
