# AWS official architecture and published cost reference

This input is a public **reference-reproduction fixture**, not a live-pricing task.
Do not call AWS account APIs and do not replace the published values with current prices.

## Source

- Publisher: Amazon Web Services
- Article: *Build priority-based message processing with Amazon MQ and AWS App Runner*
- Published: 2025-11-18
- Article: <https://aws.amazon.com/blogs/architecture/build-priority-based-message-processing-with-amazon-mq-and-aws-app-runner/>
- Official architecture image from the article:

![AWS priority-based message processing architecture](https://d2908q01vomqb2.cloudfront.net/fc074d501302eb2b93e2554793fcaf50b3bf7291/2025/11/13/image-1-2.jpeg)

- Pinned AWS Samples repository diagram: <https://github.com/aws-samples/sample-amazonmq-polling-mechanism/blob/6cab865650b4080ade6aa39b8e66372074cc597f/architecture_aws.png>
- Pinned sample commit: `6cab865650b4080ade6aa39b8e66372074cc597f`

The diagram and article describe a priority-message system centered on AWS App Runner,
Amazon MQ, and Amazon DynamoDB, with real-time status updates through API Gateway
WebSocket, DynamoDB Streams, Lambda, and CloudWatch. The published cost table below
uses a narrower six-row estimation scope; services not listed in the table must be
reported as outside the published estimate rather than silently added to the total.

## AWS-published monthly estimate (US East, N. Virginia)

| Service | Small (1,000 msg/day) | Medium (10,000 msg/day) | Large (100,000 msg/day) |
|---|---:|---:|---:|
| Amazon DynamoDB | $5–10 | $25–50 | $200–400 |
| Amazon MQ | $15 (t3.micro) | $30 (m5.large) | $120 (m5.xlarge) |
| AWS App Runner | $20–40 | $50–150 | $400–800 |
| Amazon API Gateway WebSocket | $3–5 | $10–25 | $50–100 |
| Amazon CloudWatch Logs | $5–10 | $10–20 | $30–50 |
| Data Transfer | $5 | $10–20 | $50–100 |
| **Total Estimated Cost** | **$53–95** | **$135–295** | **$850–1,570** |

## Required normalization rule for this case

Use the **Medium** column. Return one representative point per service inside each
published range, and make `monthly_total_usd` equal the sum of those six points.
A midpoint is recommended but not required. Cite the AWS article for every row.
State that this is an AWS-published range snapshot, not a newly queried live price.
