import json
from pathlib import Path

root = Path("workshop/manual")
experiment = json.loads((root / "experiment.json").read_text(encoding="utf-8"))
version = input("確認したMCP package version（例: 1.0.0、latest不可）: ").strip()
if not version or version == "latest":
    raise SystemExit("Record the resolved package version before continuing")
experiment.update({
    "experiment_id": "cost-estimation-prompt-v1-pricing-mcp",
    "tool_mode": "pricing-mcp",
    "mcp_server": f"awslabs.aws-pricing-mcp-server@{version}",
    "aws_permission": "pricing:* only",
    "aws_profile": "agent-pricing-eval",
})
(root / "experiment-pricing-mcp.json").write_text(
    json.dumps(experiment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
output_dir = (root / "runs/mcp-output").resolve()
output_dir.mkdir(parents=True, exist_ok=True)
config = {"mcpServers": {"aws-pricing": {
    "type": "stdio",
    "command": "uvx",
    "args": [f"awslabs.aws-pricing-mcp-server@{version}"],
    "env": {
        "AWS_PROFILE": "agent-pricing-eval",
        "AWS_REGION": "us-east-1",
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_PRICING_MCP_OUTPUT_DIR": str(output_dir),
    },
}}}
(root / "config").mkdir(exist_ok=True)
(root / "config/pricing-mcp.json").write_text(
    json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("Created experiment-pricing-mcp.json and config/pricing-mcp.json")
