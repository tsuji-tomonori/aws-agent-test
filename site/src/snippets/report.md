# AWS Agent評価レポート

## 実施範囲

- 実施日：未記入
- Agent CLI / バージョン / モデル：未記入
- 実験条件：workshop/manual/experiment.json
- MCPあり条件（実施時）：workshop/manual/experiment-pricing-mcp.json
- プロンプト：agent-v1
- Judgeモデル：未記入
- Gold set校正：未実施

## 反復結果

各runのsummary.jsonを確認して記入する。未実施を0件成功と扱わない。

| 条件 | ケース | 試行数 | 成功数 | 成功率 | Wilson 95% CI | pass@5 | pass^5 |
|---|---|---:|---:|---|---|---|---|
| no-mcp-batch-01 | cfn-missing-usage | 未記入 | 未記入 | 未記入 | 未記入 | 未記入 | 未記入 |
| pricing-mcp-batch-01（任意） | cfn-static-site | 未記入 | 未記入 | 未記入 | 未記入 | 未記入 | 未記入 |

上の2行はケースが異なるため、MCPの優劣を比較した結果ではない。
比較実験では同じケース・同じ価格情報・同じモデルで条件を揃えて別runを作る。

## 失敗の分析

- execution / JSON・Schema / service / arithmetic / source / clarification：未記入
- Judgeの4次元スコア、critical concern、判定不一致：未記入
- 実行ログ、終了コード、入力変更の確認結果：未記入
- 所要時間 / token / 推論費用 / MCP呼び出し数：未記入（測定できない値は不明と記載）

## 再現に必要な条件

- リポジトリcommit：未記入
- CLI、モデル、MCP package version、prompt、Schema、ケースの版：未記入
- oracleのレビュー結果と価格基準日：未記入
- 判定対象：deterministic_pass AND semantic_pass
- 未実施の確認と制約：未記入

## 次に変更する一要因

- 変更対象と理由：未記入
- 新しいexperiment_id：未記入
- 中止条件と費用上限：未記入
