# 公開価格ソースと認証境界

## 結論

コスト試算というタスク自体に AWS 認証情報は必須ではありません。次はすべて認証不要です。

- リポジトリ内の固定価格スナップショットを使う評価
- AWS 公式ブログ、AWS Solutions の図・テンプレート・コストページを使う評価
- `pricing.us-east-1.amazonaws.com` の公開 offer file / region index の取得
- mock profile と GitHub Actions の全テスト

一方、AWS Price List Query/Bulk **API operation** や、現在の **AWS Pricing MCP Server** が boto3 Pricing client を通じて行う問い合わせは署名付き API 呼び出しです。その経路を選ぶ場合だけ AWS 認証情報と `pricing:*` が必要です。これはコスト試算一般の要件ではなく、選択した価格取得ツールの要件です。

## 価格・資料取得モード

| モード | AWS認証 | 用途 | 再現性 |
|---|---:|---|---|
| frozen snapshot | 不要 | CI、回帰、モデル比較 | 高い |
| AWS公式 public asset / cost page | 不要 | 公式 reference 検証 | URL、取得日時、digest を固定 |
| public Price List offer files | 不要 | 最新公開価格の調査 | version URL、SKU/filter、digest を固定 |
| AWS Price List API / Pricing MCP | `pricing:*` | API/MCP連携そのものの評価 | client/MCP版、filter、取得日時を固定 |

## 公開 offer file

例:

```text
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/index.json
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json
https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/region_index.json
```

URL の構築には次を使います。

```bash
aws-agent-eval public-price-url --service-code AmazonRDS
aws-agent-eval public-price-url --service-code AmazonRDS --region-code us-east-1
aws-agent-eval public-price-url --service-code AmazonRDS --region-index
```

`current` は将来内容が変わるため、oracle 作成時には取得日、レスポンス digest、必要なら versioned URL を provenance に保存します。

## AWS公式 architecture assets

`datasets/aws-official-solutions-v1` の `public_assets` はすべて `authentication: none` です。`fetch-assets` は HTTPS allowlist、media type、size、redirect 先を検査し、SHA-256 lock を作ります。

```bash
aws-agent-eval fetch-assets \
  --dataset datasets/aws-official-solutions-v1 \
  --cache-dir asset-cache
```

AWS の cost page は評価側の oracle provenance であり、Agent に直接渡す asset ではありません。

## MCP profile の分離

標準 profile:

- `config/profiles/claude-code.json`
- `config/profiles/codex.json`

これらは AWS 認証情報を要求せず、`AWS_EC2_METADATA_DISABLED=true` を設定します。

MCP 専用 profile:

- `config/profiles/claude-code-pricing-mcp.json`
- `config/profiles/codex-pricing-mcp.json`

これらだけが `AWS_PROFILE`、`AWS_REGION`、`uvx` を前提にします。デプロイ権限を追加して認証エラーを解消してはいけません。
