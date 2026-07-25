# データセット作成手順

## 1. ケース設計表を先に作る

追加前に、少なくとも次の軸を表にして偏りを確認します。

- 入力: CloudFormation / CDK / architecture diagram / public reference
- 課金: リクエスト、実行時間、保存量、転送量、常時稼働、複合単価
- 入力品質: 完全、曖昧、必須値欠落、矛盾
- 出力期待: 完了、確認要求、未対応
- サービス種別: compute、storage、database、network、observability
- ケース種別: hidden estimation / official-reference holdout / public reference reproduction
- 価格取得: frozen snapshot / public offer file / optional Pricing MCP

## 2. hidden estimation ケース

1. `datasets/<dataset-id>/cases/<case-id>/input/` に最小の IaC を置く。
2. `case.json` にタスク、region、usage profile、pricing basis を記述する。
3. `expected` に必要サービス、必須仮定、必須一次 URL、期待状態、許容レンジを書く。
4. `price_snapshot` に価格の基準日と一次情報 URL を残す。
5. `dataset.json` にケースを追加し、Semantic Version を更新する。

Agent に渡す入力だけで問題が解けることを確認します。非公開 `expected` や oracle は `input/` へ置きません。

## 3. AWS公式図 + 公表コストを使う holdout ケース

`datasets/aws-official-solutions-v1` は、AWS が公開する次の三点を結び付けます。

1. 公式アーキテクチャ図
2. 公式 CloudFormation テンプレート
3. 同じ reference scenario に対する AWS 公表コスト表

`case.json` では次の契約を使います。

- `public_assets`: Agent が読める図・テンプレートの公開 HTTPS URL、出典ページ、ローカル配置先、media type、`authentication: none`
- `official_reference`: solution 名、architecture/cost/template ページ、採録日、`credentials_required: false`
- `usage_profile`: AWS コストページに書かれた利用条件。ただし金額は含めない
- `oracle`: AWS 公表のサービス別金額と合計
- `expected`: 公表額を丸め誤差または明示した許容率で囲んだ決定的レンジ

コストページは `price_snapshot.sources` と oracle の provenance に保存しますが、`public_assets` には含めません。これにより、公開情報を ground truth として使いながら、試行時の答え漏洩を防ぎます。

図・テンプレートは原則として Git に複製せず、次で匿名 HTTPS 取得します。

```bash
aws-agent-eval fetch-assets \
  --dataset datasets/aws-official-solutions-v1 \
  --cache-dir asset-cache
```

生成される `assets.lock.json` には URL、SHA-256、ETag、Last-Modified、取得日時を残します。再試行時は `--asset-cache asset-cache` で digest 検証済みのローカルコピーを trial workspace へ渡します。

## 4. public reference reproduction ケース

AWS 公式ブログや公式 sample repository の公開図と、すでに公開された見積もり結果を Agent 入力にも含め、構造化再現性を評価します。

- `input/` には公開図の固定 URL、公開表、対象 tier、変換規則を置く。
- `provenance_files` には publisher、公開日、固定 commit、diagram path/blob SHA、license、転記した表、既知の不整合を保存する。
- `tags` に `reference-reproduction` を付ける。
- 公開レンジを Agent に渡すため、hidden estimation / official-reference holdout の精度指標へ混ぜない。
- 公開資料の数値を都合よく修正せず、矛盾は `integrity_notes` に残す。

## 5. oracle を独立作成する

作成者と確認者を分け、IaC・図から課金対象を抽出し、usage を価格単位へ変換し、単価・tier・region・購入形態を特定してサービス別式を計算します。もう1名が一次資料から独立再計算し、差異を解消してからレンジを確定します。

AWS公式 holdout では、公表表の行と転記した oracle を機械的に合計し、AWS の表示合計との差を `review_notes` に残します。例えば表示が小数第2位へ丸められている場合、公表値を改変せずに許容誤差へ反映します。

## 6. 公開 Price List ファイル

AWS認証なしで public offer file を使えます。oracle に採用する際は `current` URL だけでなく、取得日、digest、service code、region、採用 SKU/filter を保存します。

```bash
aws-agent-eval public-price-url --service-code AmazonRDS --region-code us-east-1
```

AWS Price List Query/Bulk API を呼ぶ方式と、公開 URL を直接取得する方式は分けて記録します。前者は署名付き API 呼び出しのため認証が必要ですが、後者は不要です。

## 7. 情報不足ケース

情報不足ケースには、期待する `required_missing_input_ids` を安定 ID として列挙します。自然文の完全一致ではなく ID を比較します。

## 8. 漏洩防止

- hidden estimation / official-reference holdout では `expected`、レンジ、oracle、cost page を prompt に含めない。
- live Agent のワークスペースへ `case.json` と `provenance_files` をコピーしない。
- `TASK.md` に oracle URL が入っていないことをテストする。
- reference reproduction では公開答えを含むことを明記する。
- Judge に profile/model 名を渡さない。
- 公開データセットで学習済みの可能性が高くなったら、新しい holdout version を作る。

## 9. 更新ルール

- 価格変更だけでも dataset patch version を上げる。
- ケース追加は minor version、契約破壊は major version。
- AWS の `latest` asset が変わった場合は lock digest の差分をレビューし、必要なら dataset version を上げる。
- 過去 run の再現性のため、公開済み dataset version は上書きせず新 version を作る。
- PR には価格根拠、独立計算者、検証コマンド、asset digest、差分理由を記録する。
