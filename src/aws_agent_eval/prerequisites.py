from __future__ import annotations

import os
import shutil
from typing import Any

from .types import JsonObject


def check_prerequisites(profile: JsonObject) -> JsonObject:
    commands: list[dict[str, Any]] = []
    ok = True
    for command in profile["required_commands"]:
        path = shutil.which(str(command))
        present = path is not None
        commands.append({"name": command, "present": present, "path": path})
        ok = ok and present

    environment: list[dict[str, Any]] = []
    for name in profile["required_environment"]:
        value = os.environ.get(str(name))
        present = bool(value)
        environment.append({"name": name, "present": present})
        ok = ok and present

    return {"ok": ok, "profile": profile["name"], "commands": commands, "environment": environment}
