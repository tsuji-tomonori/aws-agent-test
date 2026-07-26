# Cost Estimation Patterns

Use the **awspricing** MCP server to get accurate cost estimates before generating IaC.

## Workflow

1. Identify all AWS services in the architecture
2. Query pricing for each service
3. Calculate monthly estimates based on expected usage
4. Present total before proceeding

## Service Codes

| Service | Code | Notes |
|---|---|---|
| Fargate | `AmazonECS` | Filter by `usagetype` containing "Fargate" |
| ALB | `AWSELB` | Application Load Balancer |
| S3 | `AmazonS3` | Storage and requests |
| CloudFront | `AmazonCloudFront` | CDN distribution |
| Lambda | `AWSLambda` | Requests and duration |
| DynamoDB | `AmazonDynamoDB` | On-demand or provisioned |

## Fargate Pricing

Fargate charges per vCPU-hour and per GB-hour. Query with usage-type filters.

## Presenting Estimates

Always show:

1. Per-service breakdown
2. Monthly total
3. Key assumptions
4. Cost optimization tips if relevant
