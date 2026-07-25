# セキュリティとコスト制御

## 脅威モデル

主なリスクは次です。

- Agent が見積もりを越えて AWS 変更操作を行う
- 不要な AWS 認証情報を読み込む、または秘密を transcript に含める
- IaC 内の命令文を prompt injection として実行する
- 外部 asset の redirect、巨大ファイル、path traversal を利用される
- MCP の出力先がワークスペース外へ逸脱する
- 無制限の turn、timeout、反復で推論費用が膨らむ
- account-specific な情報が評価成果物へ混入する
- hidden oracle や AWS cost page が Agent workspace へ漏れる

## 実装済み制御

- ケースごと・trial ごとの隔離ワークスペース
- 非公開 oracle、expected、price snapshot、provenance を live workspace へコピーしない
- AWS公式 holdout の cost page を prompt/public asset へ含めない
- prompt で read-only と非デプロイを明示
- 標準 profile は AWS 認証情報を要求しない
- `AWS_EC2_METADATA_DISABLED=true` により標準 profile の不要なメタデータ認証探索を抑止
- Pricing MCP profile を標準 profile から分離
- public asset は HTTPS allowlist、最終 redirect host、media type、50 MiB 上限、safe relative path を検査
- asset lock の SHA-256 を trial 配置前に再検証
- profile ごとの timeout
- 明示した repetitions のみ実行
- stdout/stderr/response/result を trial 単位で保存
- `runs/` と `asset-cache/` を Git 管理対象外に設定
- GitHub Actions は mock profile のみ。外部 asset を CI では取得しない
- MCP profile では `AWS_PRICING_MCP_OUTPUT_DIR` を trial workspace に限定

## 標準運用

- frozen snapshot または公開 AWS 資料を優先する
- AWS認証を使わない経路で解けるタスクに認証情報を渡さない
- Agent CLI 側の tool allowlist / sandbox を確認する
- 社内 IaC をケースへ追加する前に秘密・顧客情報を除去する
- live run の最大 turn、timeout、repetitions をレビューする
- transcript を共有する前に秘密情報を検査する
- AWS の `latest` asset を更新した場合は digest 差分と構成差分をレビューする

## Pricing MCP を選択する場合

- 一時クレデンシャルを使う
- AWS Pricing MCP に必要な `pricing:*` 以外を与えない
- profile 名、MCP version、filter、取得日時を run evidence に残す
- 認証失敗をデプロイ権限の追加で解決しない

## 推論費用

Agent が返す `agent_metrics.model_cost_usd` は参考値です。provider 側の利用記録が正本であり、report では両者を混同しません。pilot は1ケース1回から始め、本測定の反復数は pilot の時間・費用を見て決定します。

## AWS 利用料金

公開価格資料、AWS公式図、公開 CloudFormation テンプレート、公開 offer file の参照は AWS リソース作成を必要としません。本実験は見積もりのために stack を deploy しません。Pricing MCP を使う場合も、権限は価格情報参照に限定します。
