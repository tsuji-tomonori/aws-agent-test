from __future__ import annotations

import json
from pathlib import Path

from .types import Case, JsonObject


def render_agent_prompt(
    case: Case,
    template_path: Path,
    public_assets: list[JsonObject] | None = None,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "{{CASE_ID}}": case.id,
        "{{IAC_TYPE}}": str(case.data["iac_type"]),
        "{{REGION}}": str(case.data["region"]),
        "{{TASK}}": str(case.data["task"]),
        "{{INPUT_FILES}}": ", ".join(str(item) for item in case.data["inputs"]),
        "{{USAGE_PROFILE}}": json.dumps(
            case.data["usage_profile"], ensure_ascii=False, indent=2, sort_keys=True
        ),
        "{{PRICING_BASIS}}": json.dumps(
            case.data["pricing_basis"], ensure_ascii=False, indent=2, sort_keys=True
        ),
        "{{PUBLIC_ASSETS}}": json.dumps(
            public_assets if public_assets is not None else case.data.get("public_assets", []),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    }
    rendered = template
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    unresolved = [part for part in replacements if part in rendered]
    if unresolved:
        raise ValueError(f"Unresolved prompt markers: {unresolved}")
    return rendered
