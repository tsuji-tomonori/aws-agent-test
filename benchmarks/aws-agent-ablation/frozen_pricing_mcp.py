from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "frozen-aws-pricing-benchmark",
    instructions=(
        "Read-only benchmark pricing lookup. It returns frozen public AWS unit prices "
        "and required missing inputs, never oracle totals."
    ),
)

CASES: dict[str, dict[str, Any]] = {
    "cfn-serverless-api": {
        "effective_at": "2026-07-25",
        "region": "us-east-1",
        "dimensions": [
            {"service": "AWS Lambda", "name": "requests", "unit": "million requests", "unit_price_usd": 0.20, "source_url": "https://aws.amazon.com/lambda/pricing/"},
            {"service": "AWS Lambda", "name": "compute", "unit": "GB-second", "unit_price_usd": 0.0000166667, "source_url": "https://aws.amazon.com/lambda/pricing/"},
            {"service": "Amazon API Gateway", "name": "HTTP API requests", "unit": "million requests", "unit_price_usd": 1.00, "source_url": "https://aws.amazon.com/api-gateway/pricing/"},
            {"service": "Amazon DynamoDB", "name": "write request units", "unit": "million WRU", "unit_price_usd": 0.625, "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/"},
            {"service": "Amazon DynamoDB", "name": "read request units", "unit": "million RRU", "unit_price_usd": 0.125, "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/"},
        ],
        "required_missing_inputs": [],
    },
    "cfn-static-site": {
        "effective_at": "2026-07-25",
        "region": "us-east-1",
        "dimensions": [
            {"service": "Amazon S3", "name": "Standard storage", "unit": "GB-month", "unit_price_usd": 0.023, "source_url": "https://aws.amazon.com/s3/pricing/"},
            {"service": "Amazon S3", "name": "PUT requests", "unit": "thousand requests", "unit_price_usd": 0.005, "source_url": "https://aws.amazon.com/s3/pricing/"},
            {"service": "Amazon S3", "name": "GET requests", "unit": "thousand requests", "unit_price_usd": 0.0004, "source_url": "https://aws.amazon.com/s3/pricing/"},
            {"service": "Amazon CloudFront", "name": "US/Canada/Mexico transfer out", "unit": "GB", "unit_price_usd": 0.085, "source_url": "https://aws.amazon.com/cloudfront/pricing/"},
            {"service": "Amazon CloudFront", "name": "HTTPS requests", "unit": "ten-thousand requests", "unit_price_usd": 0.01, "source_url": "https://aws.amazon.com/cloudfront/pricing/"},
        ],
        "required_missing_inputs": [],
    },
    "cdk-fargate-alb": {
        "effective_at": "2026-07-25",
        "region": "us-east-1",
        "dimensions": [
            {"service": "AWS Fargate", "name": "vCPU", "unit": "vCPU-hour", "unit_price_usd": 0.04048, "source_url": "https://aws.amazon.com/fargate/pricing/"},
            {"service": "AWS Fargate", "name": "memory", "unit": "GB-hour", "unit_price_usd": 0.004445, "source_url": "https://aws.amazon.com/fargate/pricing/"},
            {"service": "Elastic Load Balancing", "name": "ALB hours", "unit": "ALB-hour", "unit_price_usd": 0.0225, "source_url": "https://aws.amazon.com/elasticloadbalancing/pricing/"},
            {"service": "Elastic Load Balancing", "name": "LCU hours", "unit": "LCU-hour", "unit_price_usd": 0.008, "source_url": "https://aws.amazon.com/elasticloadbalancing/pricing/"},
        ],
        "required_missing_inputs": [],
    },
    "cfn-missing-usage": {
        "effective_at": "2026-07-25",
        "region": "us-east-1",
        "dimensions": [],
        "required_missing_inputs": [
            "monthly_api_requests",
            "monthly_lambda_requests",
            "lambda_average_duration_ms",
            "monthly_dynamodb_write_request_units",
            "monthly_dynamodb_read_request_units",
        ],
    },
}


@mcp.tool()
def get_case_price_dimensions(case_id: str) -> dict[str, Any]:
    """Return frozen public unit prices or missing-input IDs for one benchmark case.

    This tool deliberately does not return service subtotals, the expected total,
    accepted ranges, or any hidden evaluation result.
    """
    if case_id not in CASES:
        return {"error": "unknown_case", "case_id": case_id, "known_case_ids": sorted(CASES)}
    return {"case_id": case_id, **CASES[case_id]}


if __name__ == "__main__":
    mcp.run()
