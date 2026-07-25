from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .types import JsonObject
from .utils import load_json


class SchemaValidationError(ValueError):
    pass


def validate_object(instance: Any, schema_path: Path, *, label: str) -> None:
    schema: JsonObject = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    messages: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        messages.append(f"{location}: {error.message}")
    raise SchemaValidationError(f"{label} failed schema validation:\n- " + "\n- ".join(messages))
