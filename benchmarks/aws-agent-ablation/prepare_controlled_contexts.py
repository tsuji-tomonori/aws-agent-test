from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

KNOWLEDGE_URL = "https://knowledge-mcp.global.api.aws"
QUERIES = {
    "cfn-serverless-api": (
        "AWS Lambda HTTP API API Gateway DynamoDB on-demand pricing dimensions "
        "requests duration GB-second read request units write request units"
    ),
    "cfn-static-site": (
        "Amazon S3 CloudFront pricing dimensions standard storage PUT GET requests "
        "HTTPS requests data transfer out US Canada Mexico"
    ),
    "cdk-fargate-alb": (
        "AWS Fargate Application Load Balancer pricing dimensions vCPU hour memory "
        "GB hour ALB hour LCU hour"
    ),
    "cfn-missing-usage": (
        "AWS Lambda API Gateway DynamoDB cost estimate required usage inputs requests "
        "duration memory read and write request units"
    ),
}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


async def _prepare_knowledge(root: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "server": KNOWLEDGE_URL,
        "prepared_at": datetime.now(UTC).isoformat(),
        "cases": {},
    }
    try:
        async with streamable_http_client(KNOWLEDGE_URL) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                await asyncio.wait_for(session.initialize(), timeout=60)
                tools = await asyncio.wait_for(session.list_tools(), timeout=30)
                metadata["tools"] = [_jsonable(tool) for tool in tools.tools]
                for case_id, query in QUERIES.items():
                    try:
                        result = await asyncio.wait_for(
                            session.call_tool(
                                "search_documentation",
                                {
                                    "search_phrase": query,
                                    "topics": ["general"],
                                    "limit": 3,
                                },
                            ),
                            timeout=60,
                        )
                        value = {
                            "case_id": case_id,
                            "query": query,
                            "server": KNOWLEDGE_URL,
                            "tool": "search_documentation",
                            "result": _jsonable(result),
                        }
                    except Exception as exc:  # noqa: BLE001
                        value = {
                            "case_id": case_id,
                            "query": query,
                            "server": KNOWLEDGE_URL,
                            "tool": "search_documentation",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    _write(root / "knowledge" / f"{case_id}.json", value)
                    metadata["cases"][case_id] = {
                        "ok": "error" not in value,
                        "path": f"knowledge/{case_id}.json",
                    }
    except Exception as exc:  # noqa: BLE001
        metadata["startup_error"] = f"{type(exc).__name__}: {exc}"
        for case_id, query in QUERIES.items():
            value = {
                "case_id": case_id,
                "query": query,
                "server": KNOWLEDGE_URL,
                "tool": "search_documentation",
                "error": metadata["startup_error"],
            }
            _write(root / "knowledge" / f"{case_id}.json", value)
            metadata["cases"][case_id] = {
                "ok": False,
                "path": f"knowledge/{case_id}.json",
            }
    return metadata


async def _prepare_pricing(root: Path, server_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    ):
        env.pop(key, None)
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=env,
    )
    metadata: dict[str, Any] = {
        "server": str(server_path),
        "prepared_at": datetime.now(UTC).isoformat(),
        "cases": {},
    }
    try:
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await asyncio.wait_for(session.initialize(), timeout=30)
                tools = await asyncio.wait_for(session.list_tools(), timeout=30)
                metadata["tools"] = [_jsonable(tool) for tool in tools.tools]
                for case_id in QUERIES:
                    try:
                        result = await asyncio.wait_for(
                            session.call_tool(
                                "get_case_price_dimensions", {"case_id": case_id}
                            ),
                            timeout=30,
                        )
                        value = {
                            "case_id": case_id,
                            "server": "frozen-public-unit-price-mcp",
                            "tool": "get_case_price_dimensions",
                            "result": _jsonable(result),
                        }
                    except Exception as exc:  # noqa: BLE001
                        value = {
                            "case_id": case_id,
                            "server": "frozen-public-unit-price-mcp",
                            "tool": "get_case_price_dimensions",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    _write(root / "pricing" / f"{case_id}.json", value)
                    metadata["cases"][case_id] = {
                        "ok": "error" not in value,
                        "path": f"pricing/{case_id}.json",
                    }
    except Exception as exc:  # noqa: BLE001
        metadata["startup_error"] = f"{type(exc).__name__}: {exc}"
        for case_id in QUERIES:
            value = {
                "case_id": case_id,
                "server": "frozen-public-unit-price-mcp",
                "tool": "get_case_price_dimensions",
                "error": metadata["startup_error"],
            }
            _write(root / "pricing" / f"{case_id}.json", value)
            metadata["cases"][case_id] = {
                "ok": False,
                "path": f"pricing/{case_id}.json",
            }
    return metadata


async def _main(output: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=True)
    knowledge, pricing = await asyncio.gather(
        _prepare_knowledge(output),
        _prepare_pricing(
            output,
            repo_root / "benchmarks/aws-agent-ablation/frozen_pricing_mcp.py",
        ),
    )
    _write(
        output / "context-preparation.json",
        {
            "schema_version": "1.0",
            "prepared_at": datetime.now(UTC).isoformat(),
            "knowledge": knowledge,
            "pricing": pricing,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(_main(args.output.resolve()))


if __name__ == "__main__":
    main()
