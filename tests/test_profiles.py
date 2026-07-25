from pathlib import Path

from aws_agent_eval.runner import load_profile


ROOT = Path(__file__).resolve().parents[1]


def test_default_live_profiles_do_not_require_aws_credentials() -> None:
    for name in ("claude-code.json", "codex.json"):
        profile = load_profile(ROOT / "config/profiles" / name)
        assert profile["required_environment"] == []
        assert "aws" not in profile["required_commands"]
        assert "uvx" not in profile["required_commands"]
        assert profile["environment"]["AWS_EC2_METADATA_DISABLED"] == "true"


def test_pricing_mcp_profiles_are_explicit_and_minimally_scoped() -> None:
    for name in ("claude-code-pricing-mcp.json", "codex-pricing-mcp.json"):
        profile = load_profile(ROOT / "config/profiles" / name)
        assert profile["required_environment"] == ["AWS_PROFILE", "AWS_REGION"]
        assert "uvx" in profile["required_commands"]
        assert "AWS_PRICING_MCP_OUTPUT_DIR" in profile["environment"]
