from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Case:
    path: Path
    data: JsonObject

    @property
    def id(self) -> str:
        return str(self.data["id"])


@dataclass(frozen=True)
class Dataset:
    root: Path
    data: JsonObject
    cases: tuple[Case, ...]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def version(self) -> str:
        return str(self.data["version"])
