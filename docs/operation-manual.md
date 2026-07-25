# チーム展開用操作マニュアル

## 対象者

Python とコマンドラインの基本操作ができるメンバーを対象にします。標準試行に AWS アカウントや AWS 認証情報は不要です。

## 1. 初回セットアップ

```bash
git clone https://github.com/tsuji-tomonori/aws-agent-test.git
cd aws-agent-test
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows では WSL からの実行を推奨します。

## 2. offline で確認する

```bash
aws-agent-eval validate --dataset datasets/aws-cost-v1
aws-agent-eval validate --dataset datasets/aws-official-solutions-v1

aws-agent-eval experiment \
  --dataset datasets/aws-official-solutions-v1 \
  --profile config/profiles/mock.json \
  --repetitions 3 \
  --run-dir runs/onboarding-official-mock
aws-agent-eval report --run-dir runs/onboarding-official-mock
```

公式3ケースすべてが `pass^3` を満たせば、Python、Schema、runner、evaluator、reporter の配線は正常です。この工程にネットワークも AWS 認証情報も不要です。

## 3. AWS公式 asset を匿名取得する

```bash
aws-agent-eval fetch-assets \
  --dataset datasets/aws-official-solutions-v1 \
  --cache-dir asset-cache
```

次を確認します。

- `asset-cache/aws-official-solutions-v1/1.0.0/assets.lock.json` が存在する
- 3ケース × 図/テンプレート = 6 asset の SHA-256 が記録されている
- AWS profile を設定していなくても成功する

公開 URL の内容は将来更新され得るため、`assets.lock.json` は run evidence として保存します。通常は Git へ commit しません。

## 4. AWS Agent Plugins を導入する

### Claude Code

```text
/plugin marketplace add awslabs/agent-plugins
/plugin install deploy-on-aws@agent-plugins-for-aws
```

### Codex

1. `git clone https://github.com/awslabs/agent-plugins.git` を実行する。
2. clone したリポジトリを Codex で開く。
3. 再起動する。
4. `Agent Plugins for AWS` marketplace から `deploy-on-aws` をインストールする。
5. 本リポジトリへ戻る。

## 5. AWS認証不要の live pilot

Claude Code / Codex 自体の認証は必要ですが、AWS profile は不要です。

```bash
aws-agent-eval check-prerequisites --profile config/profiles/claude-code.json

aws-agent-eval experiment \
  --dataset datasets/aws-official-solutions-v1 \
  --profile config/profiles/claude-code.json \
  --asset-cache asset-cache \
  --case official-instance-scheduler-small \
  --repetitions 1 \
  --run-dir runs/pilot-official
aws-agent-eval report --run-dir runs/pilot-official
```

`--asset-cache` を省略した場合は `TASK.md` に AWS 公開 URL が入り、Agent 自身が読みます。どちらも AWS API は呼びません。コストページと oracle は Agent workspace に入りません。

## 6. AWS Pricing MCP の連携自体を試す場合

この工程だけはオプションです。

```bash
export AWS_PROFILE=agent-pricing-eval
export AWS_REGION=us-east-1

aws-agent-eval check-prerequisites \
  --profile config/profiles/claude-code-pricing-mcp.json
```

認証情報は短期化し、権限は `pricing:*` に限定します。CloudFormation、CDK deploy、IAM、EC2、S3 等の変更権限は付けません。

## 7. チーム試行の記録

各メンバーは次を記録します。

- OS / shell / Python version
- Agent CLI version
- model
- AWS Agent Plugins commit/version
- dataset ID/version
- profile file digest
- asset lock digest
- 価格取得モード（frozen / public / Pricing MCP）
- AWS認証を使ったか、使った場合の権限境界
- 所要時間と推論費用
- セットアップで迷った箇所
- 再実行できたか

同一手順を2人以上が独立実行し、口頭補助なしで mock run と認証不要 pilot を完了できることを「展開可能」の最低条件とします。

## 8. トラブルシュート

### 標準 profile が AWS 認証を求める

Agent が AWS Pricing MCP や AWS CLI を自動選択していないか確認します。標準 profile は公開資料・公開 Price List を使う経路です。AWS権限を追加せず、prompt と tool selection を修正します。

### asset download に失敗する

出典ページをブラウザで確認し、AWS の `latest` URL が変更されていないか確認します。URL allowlist、HTTPS、Content-Type、50 MiB 上限、redirect 先、proxy を調査します。認証情報を追加して解決しません。

### Pricing MCP が認証に失敗する

MCP 専用 profile を選んだ場合だけ、`AWS_PROFILE`、一時認証情報の期限、`pricing:*`、`AWS_REGION` を確認します。デプロイ権限を追加して解決しないでください。

### JSON Schema error

Agent の自然文ではなく `response.json` を確認します。profile の parser が CLI 出力形式と合っているか、Agent が Markdown fence を付けていないかを確認します。

### 数値が毎回変わる

価格取得モード、取得日時、SKU/filter、region、usage tier、Free Tier の扱いを比較します。単にレンジを広げず、変動原因を failure taxonomy に追加します。
