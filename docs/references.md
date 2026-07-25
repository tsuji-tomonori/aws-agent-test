# 根拠・参考資料

本リポジトリの設計・運用で参照した一次資料です。URL、参照日、必要に応じて commit/digest を記録します。

## AWS Agent / Pricing

- Agent Plugins for AWS: <https://github.com/awslabs/agent-plugins>
- `deploy-on-aws` plugin: <https://github.com/awslabs/agent-plugins/tree/main/plugins/deploy-on-aws>
- AWS Pricing MCP Server: <https://github.com/awslabs/mcp/tree/main/src/aws-pricing-mcp-server>
- AWS Price List Bulk API: <https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api.html>
- AWS Price List files — manual public download: <https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api-fetching-price-list-files-manually.html>
- AWS public price update / offer-file URL examples: <https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/notifications-price-list-api.html>

## AWS Solutions official-reference holdout

### Instance Scheduler on AWS

- Architecture: <https://docs.aws.amazon.com/solutions/latest/instance-scheduler-on-aws/architecture.html>
- CloudFormation templates: <https://docs.aws.amazon.com/solutions/latest/instance-scheduler-on-aws/aws-cloudformation-templates.html>
- Cost reference examples: <https://docs.aws.amazon.com/solutions/latest/instance-scheduler-on-aws/cost.html>

### Cloud Migration Factory on AWS

- Architecture: <https://docs.aws.amazon.com/solutions/latest/cloud-migration-factory-on-aws/architecture-overview.html>
- CloudFormation templates: <https://docs.aws.amazon.com/solutions/latest/cloud-migration-factory-on-aws/aws-cloudformation-templates.html>
- Cost: <https://docs.aws.amazon.com/solutions/latest/cloud-migration-factory-on-aws/cost.html>

### Landing Zone Accelerator on AWS

- Architecture: <https://docs.aws.amazon.com/solutions/latest/landing-zone-accelerator-on-aws/architecture-overview.html>
- CloudFormation template: <https://docs.aws.amazon.com/solutions/latest/landing-zone-accelerator-on-aws/aws-cloudformation-template.html>
- Cost: <https://docs.aws.amazon.com/solutions/latest/landing-zone-accelerator-on-aws/cost.html>
- Sample configuration repository: <https://github.com/awslabs/landing-zone-accelerator-on-aws>

## AWS公式 public reference-reproduction fixture

- AWS Architecture Blog: <https://aws.amazon.com/blogs/architecture/build-priority-based-message-processing-with-amazon-mq-and-aws-app-runner/>
- AWS Samples repository: <https://github.com/aws-samples/sample-amazonmq-polling-mechanism>
- Pinned sample commit: `6cab865650b4080ade6aa39b8e66372074cc597f`
- Pinned repository diagram: <https://github.com/aws-samples/sample-amazonmq-polling-mechanism/blob/6cab865650b4080ade6aa39b8e66372074cc597f/architecture_aws.png>
- Blog architecture image: <https://d2908q01vomqb2.cloudfront.net/fc074d501302eb2b93e2554793fcaf50b3bf7291/2025/11/13/image-1-2.jpeg>

## Pricing pages used by hidden estimation cases

- Lambda: <https://aws.amazon.com/lambda/pricing/>
- API Gateway: <https://aws.amazon.com/api-gateway/pricing/>
- DynamoDB: <https://aws.amazon.com/dynamodb/pricing/on-demand/>
- S3: <https://aws.amazon.com/s3/pricing/>
- CloudFront: <https://aws.amazon.com/cloudfront/pricing/>
- Fargate: <https://aws.amazon.com/fargate/pricing/>
- Elastic Load Balancing: <https://aws.amazon.com/elasticloadbalancing/pricing/>

## Agent evaluation

- τ-bench: Tool-Agent-User Interaction in Real-World Domains: <https://arxiv.org/abs/2406.12045>
- AgentBench: Evaluating LLMs as Agents: <https://arxiv.org/abs/2308.03688>
- Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena: <https://arxiv.org/abs/2306.05685>

## 実装へ反映した要点

- 1回成功ではなく反復信頼性を測る。
- Agent の最終回答だけでなく、ツール・価格根拠・仮定を監査可能にする。
- 客観条件は deterministic evaluator、意味品質は校正済み Judge に分離する。
- コスト試算一般と、AWS Price List API / Pricing MCP 固有の認証要件を分離する。
- official-reference holdout、public reference reproduction、hidden estimation を別の能力として扱う。
