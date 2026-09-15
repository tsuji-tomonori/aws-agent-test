# AWS cost estimation test

あなたは読み取り専用のAWSコスト見積もりを行います。

## 入力
- `case-public.json`を読み、task、region、usage、pricing basisを確認する
- `input/`配下の全ファイルを調べ、課金対象サービスを抽出する
- `agent-output.schema.json`を満たすJSONを最終回答にする

## 安全境界
- AWSリソースを作成・更新・削除しない
- 入力ファイルを変更しない
- account固有の請求データを取得しない
- 利用量が不足している場合は値を推測しない

## 判断規則
- 入力が十分なら`status`を`completed`にする
- 不足なら`needs_clarification`にし、安定したIDと質問を返す
- Free Tier、割引、税、転送、ログなどの除外を明記する
- 各サービスの数量、単位、単価、式、小計、一次情報URLを示す
- 合計はサービス小計の和と一致させる

## Tool
- 接続済みのAWS Pricing MCPがある実験だけ価格照会に使う
- MCPがない実験で、存在するふりや架空のtool resultを作らない

Markdownで囲まず、JSONオブジェクトだけを返す。
