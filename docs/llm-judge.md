# LLM Judge の構築・校正

## 1. 役割を限定する

Judge が扱うのは説明の意味品質だけです。価格の正誤、合計、Schema、必須サービス、確認質問 ID は決定的 evaluator の責務です。この境界により、Judge の気分やモデル更新で客観的合否が逆転することを防ぎます。

## 2. 固定ルーブリック

`prompts/judge.md` と `schemas/judge-output.schema.json` を版管理します。

| 次元 | 1 | 3 | 5 |
|---|---|---|---|
| 仮定 | 暗黙・矛盾 | 主な仮定を列挙 | 仮定、根拠、影響が結び付く |
| 不確実性 | 推測を断定 | 主な曖昧さを記載 | 不足時に質問し、感度も説明 |
| 除外事項 | なし | 主な除外を列挙 | 境界と影響を明確化 |
| 行動可能性 | 再現不能 | 概ね追跡可能 | 第三者が更新・反証できる |

`semantic_pass` は全次元3以上かつ critical concern なしの場合だけ true とします。

## 3. 匿名化と反復

```bash
aws-agent-eval prepare-judge --run-dir runs/claude-live --repeats 3
```

`judge/batch.jsonl` には profile/model 名を含めません。各 `judge_item_id` を3回判定し、順序をランダム化して Judge に渡します。

Judge の応答を1行1 JSONで `judge/judgments.jsonl` に保存し、次を実行します。

```bash
aws-agent-eval aggregate-judge \
  --run-dir runs/claude-live \
  --input runs/claude-live/judge/judgments.jsonl
```

集計は次のルールです。

- 各次元: 中央値
- `semantic_pass`: 多数決
- critical concern: 1回でも指摘があれば保持
- 決定的 trial が不合格なら、Judge が全回 pass でも総合合格にはしない

## 4. gold set による校正

本測定前に、人間2名が合意した gold set を用意します。良い説明だけでなく、次を意図的に含めます。

- 数値は正しいが仮定が不明
- 曖昧な入力を勝手に補完
- 除外コストが重大なのに無記載
- 長いが再計算不能
- 簡潔だが完全

Judge の pass/fail、人間判定、次元スコアを比較し、false pass を最優先で調査します。校正に失敗した Judge は本番評価へ入れず、ルーブリック、few-shot 例、モデル、温度、反復数を変更して再校正します。

## 5. Judge 自体の監査記録

最低限、以下を run と同じ場所に保存します。

- Judge provider/model/version
- prompt と schema の digest
- 推論設定
- 判定回数
- gold set version と一致率
- 生の JSONL
- 集計結果

モデルを更新した場合は過去結果と混ぜず、新しい Judge profile として扱います。
