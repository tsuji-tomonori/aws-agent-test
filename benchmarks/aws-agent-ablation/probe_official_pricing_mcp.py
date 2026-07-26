from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def probe() -> dict[str, object]:
    env = os.environ.copy()
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    ):
        env.pop(key, None)
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    params = StdioServerParameters(
        command="uvx",
        args=["awslabs.aws-pricing-mcp-server@latest"],
        env=env,
    )
    result: dict[str, object] = {
        "probed_at": datetime.now(UTC).isoformat(),
        "credentials_present": False,
        "server": "awslabs.aws-pricing-mcp-server@latest",
    }
    try:
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await asyncio.wait_for(session.initialize(), timeout=60)
                tools = await asyncio.wait_for(session.list_tools(), timeout=30)
                result["tool_count"] = len(tools.tools)
                result["tools"] = [tool.name for tool in tools.tools]
                try:
                    call = await asyncio.wait_for(
                        session.call_tool("get_pricing_service_codes", {}), timeout=45
                    )
                    result["call_is_error"] = bool(call.isError)
                    result["call_content"] = [
                        getattr(item, "text", str(item)) for item in call.content
                    ]
                except Exception as exc:  # noqa: BLE001
                    result["call_exception"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        result["startup_exception"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> None:
    output = Path(sys.argv[1])
    try:
        value = asyncio.run(probe())
    except Exception as exc:  # noqa: BLE001
        value = {"fatal_exception": f"{type(exc).__name__}: {exc}"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
