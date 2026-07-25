# aws-agent-test

CloudFormation（CFn）/ AWS CDK / AWS公式アーキテクチャ資料から AWS の月額利用コストを扱うタスクを題材に、**非決定的な AI Agent を反復可能・監査可能に評価するための実験ハーネス**です。

このリポジトリでは、数値の正しさを LLM に丸投げせず、次の三層に分離して評価します。

1. **決定的ゲート**: JSON Schema、対象サービスの網羅、計算式、合計、期待レンジ、必須根拠 URL、適切な確認質問を機械判定します。
2. **反復信頼性**: 同一ケースを複数回実行し、成功率、Wilson 95%信頼区間、`pass@k`（1回以上成功）、`pass^k`（全回成功）を集計します。
3. **LLM Judge**: 仮定・除外事項・不確実性の説明品質だけを、匿名化・固定ルーブリック・複数回判定で補助評価します。数値ゲートを上書きしません。

## AWS 認証情報について

**標準テストには AWS 認証情報は不要です。** 次は匿名 HTTPS だけで実行できます。

- mock / CI / 固定価格スナップショットの評価
- AWS公式のアーキテクチャ図・CloudFormationテンプレート・コスト例を使う評価
- `pricing.us-east-1.amazonaws.com` の公開 Price List offer file の参照
- 標準の `claude-code.json` / `codex.json` profile

Claude Code や Codex 自体の認証は別途必要ですが、これは AWS アカウント認証ではありません。AWS Pricing MCP Server の連携そのものを明示的に検証するときだけ、`*-pricing-mcp.json` profile と `pricing:*` の短期認証情報を使います。

## すぐ試す

Python 3.11 以上を使用します。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

aws-agent-eval validate --dataset datasets/aws-cost-v1
aws-agent-eval validate --dataset datasets/aws-official-solutions-v1

aws-agent-eval experiment \
  --dataset datasets/aws-official-solutions-v1 \
  --profile config/profiles/mock.json \
  --repetitions 3 \
  --run-dir runs/official-mock
aws-agent-eval report --run-dir runs/official-mock
```

生成物は `runs/official-mock/report.md` と `runs/official-mock/results.json` です。

## AWS公式図・テンプレートを認証なしで取得する

公式サンプルの図と CloudFormation テンプレートはリポジトリへ無断で固定コピーせず、AWS の公開 URL と出典ページをデータセットに保持します。再現時には匿名 HTTPS で取得し、SHA-256、ETag、取得日時を lock file に記録します。

```bash
aws-agent-eval fetch-assets \
  --dataset datasets/aws-official-solutions-v1 \
  --cache-dir asset-cache

aws-agent-eval experiment \
  --dataset datasets/aws-official-solutions-v1 \
  --profile config/profiles/claude-code.json \
  --asset-cache asset-cache \
  --repetitions 1 \
  --run-dir runs/claude-official
```

`fetch-assets` に AWS CLI、AWS SDK、AWS profile は不要です。Agent が公開 URL を直接読める環境なら `--asset-cache` 自体も省略できます。

## 認証不要の公開 Price List URL

AWS が公開している offer file の URL は SDK や AWS profile を使わず構築できます。

```bash
aws-agent-eval public-price-url --service-code AmazonRDS
aws-agent-eval public-price-url --service-code AmazonRDS --region-code us-east-1
aws-agent-eval public-price-url --service-code AmazonRDS --region-index
```

このコマンドは URL を表示するだけで、AWS SDK、認証情報、アカウント API を使用しません。

## Agent live 実行（標準・AWS認証不要）

### 1. AWS Agent Plugins を導入する

Claude Code では次を実行します。

```text
/plugin marketplace add awslabs/agent-plugins
/plugin install deploy-on-aws@agent-plugins-for-aws
```

Codex では `awslabs/agent-plugins` を clone して Codex で開き、リポジトリ内の marketplace から `deploy-on-aws` をインストールします。

### 2. 前提確認と実行

```bash
aws-agent-eval check-prerequisites --profile config/profiles/claude-code.json

aws-agent-eval experiment \
  --dataset datasets/aws-official-solutions-v1 \
  --profile config/profiles/claude-code.json \
  --case official-instance-scheduler-small \
  --repetitions 3 \
  --run-dir runs/claude-public
```

標準経路では AWS profile、AWS CLI、`uvx` を前提にしません。Plugin のワークフローを利用しつつ、価格根拠は公開 AWS 資料・公開 Price List から取得させます。

## AWS Pricing MCP を明示的に評価する場合だけ

```bash
export AWS_PROFILE=agent-pricing-eval
export AWS_REGION=us-east-1

aws-agent-eval check-prerequisites \
  --profile config/profiles/claude-code-pricing-mcp.json
```

付与する権限は `pricing:*` に限定し、デプロイ権限は与えません。Codex では `config/profiles/codex-pricing-mcp.json` を使用します。MCP live 実行は GitHub Actions では動かしません。

## コマンド

| コマンド | 目的 |
|---|---|
| `validate` | データセット、ケース、期待値を Schema と整合性ルールで検証 |
| `fetch-assets` | AWS公式図・公開テンプレートを匿名 HTTPS で取得し digest lock を作成 |
| `experiment` | ケースを隔離ワークスペースで反復実行し、その場で決定的評価 |
| `report` | 成功率、信頼区間、`pass@k` / `pass^k`、失敗分類を Markdown/JSON 化 |
| `prepare-judge` | LLM Judge 用にモデル名を除いた匿名 JSONL を生成 |
| `aggregate-judge` | Judge 出力を Schema 検証し、中央値・多数決を集計 |
| `check-prerequisites` | 選択 profile の CLI・環境変数前提を確認 |
| `public-price-url` | AWS認証不要の公開 Price List URL を生成 |

## データセット

### `datasets/aws-official-solutions-v1`

AWS Solutions の公開アーキテクチャ図と公開 CloudFormation テンプレートを入力とし、AWS が同じ構成について掲載している月額見積もりを **Agent には見せない oracle** として比較します。

| ケース | AWS公式構成 | AWS公表の月額基準 |
|---|---|---:|
| `official-instance-scheduler-small` | Instance Scheduler on AWS / Small | 約 **$9.15** |
| `official-cloud-migration-factory-default` | Cloud Migration Factory on AWS / 200 servers per month | 約 **$14.31** |
| `official-landing-zone-accelerator-sandbox` | Landing Zone Accelerator + Control Tower / non-critical sandbox | **$430.22** |

各ケースは、図 URL、図の出典ページ、公開テンプレート URL、コストページ、取得基準日、サービス別公表額、利用条件を versioned JSON として保持します。コストページは oracle 側だけにあり、live Agent の `TASK.md` とワークスペースには入りません。

### `datasets/aws-cost-v1`

| ケース | 入力 | 狙い |
|---|---|---|
| `cfn-serverless-api` | CloudFormation | Lambda / HTTP API / DynamoDB の従量課金と合計計算 |
| `cfn-static-site` | CloudFormation | S3 / CloudFront、リクエスト・転送料、Free Tier 除外 |
| `cdk-fargate-alb` | CDK(TypeScript) | Fargate の vCPU/メモリ時間と ALB/LCU の複合計算 |
| `cfn-missing-usage` | CloudFormation | 情報不足時に推測せず確認質問できるか |
| `aws-official-priority-messaging-medium` | AWS公式ブログの公開図・公開コスト表 | 公開 reference の構造化再現 |

最後のケースは公開済みコストレンジを入力にも含む **reference-reproduction** です。答えを隠した推定性能とは別に集計します。

## 合否の原則

- Schema 不正、期待状態の不一致、必須サービス欠落、価格レンジ逸脱、合計不整合、必須一次 URL 欠落は **critical failure** です。
- 加重スコアは診断用であり、critical failure を相殺しません。
- 情報不足ケースでは、もっともらしい数値を出すより `needs_clarification` と必要入力 ID を返すことを正解とします。
- AWS公式 oracle は公開情報ですが、試行時の Agent には見せず、評価コードだけが読みます。
- LLM Judge は説明品質を補助判定しますが、決定的な数値・契約判定を覆せません。

## 文書

- [評価方法](docs/evaluation-methodology.md)
- [データセット作成手順](docs/dataset-authoring.md)
- [公開価格ソースと認証境界](docs/public-price-sources.md)
- [LLM Judge 構築・校正](docs/llm-judge.md)
- [チーム展開用操作マニュアル](docs/operation-manual.md)
- [セキュリティとコスト制御](docs/security-and-cost-controls.md)
- [実験記録テンプレート](docs/experiment-template.md)
- [根拠・参考資料](docs/references.md)

## 安全上の注意

本リポジトリのタスクは**見積もり専用**です。Agent へのプロンプトは AWS リソースの作成・更新・削除を禁止し、ケース入力だけをコピーした隔離ディレクトリで実行します。ただし、外部 Agent CLI と Plugin/MCP 自体の挙動は本リポジトリの管理外です。live 実行前にツール許可、ログ、送信対象を確認してください。
