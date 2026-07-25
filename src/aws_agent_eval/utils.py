from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .types import JsonObject


def load_json(path: Path) -> JsonObject:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def extract_json_object(text: str) -> JsonObject:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            candidate = "\n".join(lines[1:-1])
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:].lstrip("\r\n")
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = candidate.find("{")
        if start < 0:
            raise ValueError("No JSON object found in agent output") from None
        try:
            value, _ = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON agent output: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Agent output must be a JSON object")
    return value


def safe_relative(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {path_text}")
    return path
