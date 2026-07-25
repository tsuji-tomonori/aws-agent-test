# 評価方法

## 1. 目的と評価単位

評価対象は「モデル」単体ではなく、**モデル + Agent CLI + Plugin/Skill + 選択した価格ソース + プロンプト + 権限 + データセット**から成る実行系です。いずれかを変更した結果は別 profile / 別 run として保存します。

1 trial は「1つのケースを、前回の会話状態を引き継がずに1回実行したもの」です。同一ケースを `k` 回反復し、非決定性を観測します。

## 2. 三層評価

### 2.1 決定的ゲート

`src/aws_agent_eval/evaluator.py` が以下を機械判定します。

| 項目 | 代表条件 | critical |
|---|---|---|
| 実行 | timeout、終了コード、出力取得 | Yes |
| 契約 | Agent output JSON Schema | Yes |
| 状態 | `completed` / `needs_clarification` 等 | Yes |
| 対象網羅 | 必須 AWS サービスがすべて存在 | Yes |
| 数値 | サービス別・合計が oracle の許容レンジ内 | Yes |
| 算術 | サービス合計と月額合計が一致 | Yes |
| 一次根拠 | ケース指定の必須 URL が出力に存在 | Yes |
| 確認質問 | 情報不足 ID を漏れなく質問 | Yes |
| 仮定 | 必須仮定 ID を明示 | No（診断スコア） |
| 証跡 | サービスごとに公開 URL と取得日時 | No（診断スコア） |

critical failure が1件でもあれば不合格です。加重スコアは診断値であり、ゲートを相殺しません。

### 2.2 反復信頼性

`k` 回実行時に次を出します。

- **trial success rate**: 全 trial 中の合格率
- **Wilson 95% confidence interval**: 少数試行でも 0%/100% に過信しない区間推定
- **pass@k**: ケースごとに k 回のうち少なくとも1回合格した割合
- **pass^k**: ケースごとに k 回すべて合格した割合

実務上は「一度はできた」`pass@k` より、「繰り返しても壊れない」`pass^k` を主要指標とします。

### 2.3 LLM Judge

LLM Judge は仮定の明瞭さ、不確実性への対処、除外事項の説明、再現・レビュー可能性だけを扱います。数値、サービス網羅、Schema、合計、一次 URL は決定的コードが判定します。

## 3. ケース種別を混同しない

### hidden estimation

価格レンジと oracle を Agent に渡さず、IaC、usage、公開価格情報から推定させます。モデル・tool chain の実務能力比較に使います。

### official-reference holdout

AWS公式アーキテクチャ図、公開 CloudFormation テンプレート、金額を除いた reference usage を Agent に渡し、AWS公式コスト表を hidden oracle として比較します。`datasets/aws-official-solutions-v1` が該当します。

公開 oracle であるため将来的な学習汚染の可能性はありますが、試行ワークスペースから cost page と金額を除外することで、少なくとも直接的な答え漏洩を防ぎます。実務上は「AWS公開構成を正しく読み、同じスコープを再現できるか」の回帰指標として扱います。

### public reference reproduction

AWS が公開した図とコスト表を Agent 入力にも渡し、構造化・スコープ保持・算術整合性を評価します。一次資料の再現テストであり、答えを隠した推定能力の指標としては扱いません。`aws-official-priority-messaging-medium` が該当します。

三種類の成功率を一つの平均へ潰さず、dataset / tag 別に解釈します。

## 4. ワークスペース隔離

各 trial には独立ディレクトリを作り、Agent に渡すのは次だけです。

- `input/` 配下の IaC・usage scenario
- `public-assets/` の digest 検証済み図・テンプレート、または同じ公開 URL
- `agent-output.schema.json`
- `TASK.md`

`case.json` の非公開 `expected`、oracle、`price_snapshot`、`official_reference.cost_page_url`、`provenance_files`、他 trial の出力はコピーしません。

## 5. 推奨実験順序

1. `mock-good` で配線・Schema・集計を確認
2. `mock-flaky` で `pass@k` と `pass^k` の差を確認
3. `aws-official-solutions-v1` を mock で実行
4. 必要なら `fetch-assets` で図・テンプレートを匿名 HTTPS 取得
5. AWS認証不要の official-reference holdout を1回 live 実行
6. hidden estimation ケースを1ケース1回で pilot
7. 必要な場合だけ Pricing MCP profile を別 run で試す
8. profile と prompt を凍結して5回以上の本測定
9. 失敗を分類し、データ・プロンプト・Plugin・モデルのどこを直すか決定
10. 同一条件で再測定

## 6. 常時守る基準

- critical failure を平均点で相殺しない
- 情報不足時の「もっともらしい推測」を成功扱いしない
- 1回の成功だけで実用性を主張しない
- dataset と profile の版を揃えずに優劣を比較しない
- official-reference holdout、public reference reproduction、hidden estimation の成績を同一能力として解釈しない
- AWS認証不要の経路に認証情報を追加しない
