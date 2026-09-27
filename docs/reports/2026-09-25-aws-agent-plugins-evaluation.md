# AWS Agent Plugins 評価レポート

実施日：2026-09-25

## 1. 目的

AWS Agent Plugins の deploy-on-aws プラグインを評価しました。
評価の手法は、このリポジトリのワークショップと同じです。
問いは次の一文です。

「プラグインを入れた Claude Code は、入れない場合より AWS 月額を正しく見積もれるか。」

## 2. 先に行った手法の点検

公開中のワークショップを、初めての人の手順で最初から実行しました。
ページのコピーボタンで取れるコードを、そのまま新しいクローンで実行しました。
Codex CLI 0.154.0 と Claude Code 2.1.282 の両方で試しました。

次の6件の問題が見つかりました。
修正は Codex（codex exec）に任せ、修正後にもう一度通しで確認しました。

| ID | 章 | 問題 | 影響 |
|---|---|---|---|
| D1 | 3, 5, 7 | 出力 Schema を両方の CLI が受け付けない | 第5章で必ず止まる |
| D2 | 2, 5, 6 | 不足情報の ID 名が Agent に知らされていない | 正しい回答が10件中10件不合格になる。第7章に進めない |
| D3 | 5, 6, 7 | 試行にリポジトリの AGENTS.md が読み込まれる | 試行の条件が教材と違ってしまう |
| D4 | 5, 6, 7 | 環境エラーのあとにやり直す方法がない | 同じ run 名のまま先に進めない |
| D5 | 2, 5 | 根拠 URL を完全一致で比べている | AWS の料金ページが移動すると、正しい回答が落ちる |
| D6 | 2, 5 | 比べるサービス名が公開されていない | 「Amazon S3 (Standard)」と書いた回答が落ちる |

D1 のエラーは次のとおりです。
Codex は `schema must have a 'type' key` で止まりました。
Claude Code は `no schema with key or ref "https://json-schema.org/draft/2020-12/schema"` で止まりました。

D2 では、Agent は正しく質問して停止しました。
しかし `api_requests_per_month` のように、名前が毎回変わりました。
チェッカーは `monthly_api_requests` という決まった名前だけを合格にしていました。

修正後は、第0章から第8章まで両方の CLI で最後まで進めました。
第6章の反復は、両方の CLI で5回中5回合格しました。
既存のテストは偽の CLI を使うため、D1 と D2 を見つけられませんでした。

## 3. 実験の条件

### 3.1 固定したもの

- Agent：Claude Code 2.1.282
- モデル：claude-opus-5-5
- プロンプト：ワークショップの agent-v1（D2 修正後）
- 出力 Schema：ワークショップの CLI 用 Schema（D1 修正後）
- 反復：各条件・各ケースで5回。毎回新しい workspace と会話を使う
- 隔離：AGENTS.md、CLAUDE.md、自動記憶を読み込まない
- AWS 認証：すべて外した。AWS へのデプロイ操作はできない設定にした
- 使える道具：Read、Glob、Grep だけ。書き込みとシェルは使えない

### 3.2 比べた条件

| 条件 | 内容 |
|---|---|
| baseline | プラグインなし。MCP なし |
| plugin | deploy-on-aws 1.3.0 を読み込む。同梱の MCP 3つを使える。スキルを使うかは Agent に任せる |
| plugin-explicit | plugin と同じ。プロンプトの先頭でスキルを使うよう指示する |
| plugin-refs | plugin-explicit と同じ。スキルの参照資料があるフォルダも読めるようにする |

プラグインは awslabs/agent-plugins のコミット 097fe8a です。
同梱の MCP は awsknowledge、aws-iac-mcp-server 1.0.26、aws-pricing-mcp-server 1.1.1 です。
版を固定するため、プラグインの .mcp.json と同じ内容を明示して渡しました。

plugin-explicit と plugin-refs は、測定の途中で足しました。
plugin 条件でスキルが一度も使われなかったためです。

### 3.3 ケース

| ケース | 入力 | 正しい振る舞い | oracle |
|---|---|---|---|
| cfn-missing-usage | API Gateway、Lambda、DynamoDB。使用量なし | 推測せず質問する | 5つの不足 ID |
| cfn-static-site | S3 と CloudFront。使用量あり | 計算する | 196.83〜200.93 USD |
| cdk-fargate-alb | CDK の Fargate と内部 ALB。使用量あり | 計算する | 39.48〜41.10 USD |

cdk-fargate-alb は、データセット aws-cost-v1 から作りました。
公開入力と oracle は分けました。
このケースを選んだ理由は、スキルの参照資料に Fargate の概算値があるためです。
その数字に回答が引きずられるかを見るためです。

### 3.4 採点

決定的ゲートは、ワークショップの check_result.py です。
判定の規則は、実験の前に固定しました。
LLM Judge は Codex CLI の gpt-6-astra です。
対象の Agent と別のモデルにして、自己評価の偏りを避けました。
全60回答を匿名にして、1回答につき3回判定しました。

## 4. 結果

### 4.1 決定的ゲート（事前に決めた規則）

| 条件 | missing-usage | static-site | fargate-alb |
|---|---|---|---|
| baseline | 5/5 | 5/5 | 5/5 |
| plugin | 5/5 | 0/5 | 5/5 |
| plugin-explicit | 5/5 | 0/5 | 5/5 |
| plugin-refs | 5/5 | 1/5 | 5/5 |

5/5 の Wilson 95% 区間は 0.57〜1.00 です。
0/5 は 0.00〜0.43 です。
1/5 は 0.04〜0.62 です。

static-site の不合格は、ほとんどが根拠 URL の不一致でした。
プラグイン条件の Agent は、実際の料金ページを読みました。
CloudFront の料金は `cloudfront/pricing/pay-as-you-go/` にありました。
oracle は `cloudfront/pricing/` との完全一致を求めていました。
plugin-refs の1件は、サービス名を「Amazon S3 (Standard)」と書いて落ちました。

### 4.2 D5 と D6 を直したチェッカーでの再採点

これは感度分析です。
事前の判定は変えていません。

| 条件 | missing-usage | static-site | fargate-alb |
|---|---|---|---|
| baseline | 5/5 | 5/5 | 5/5 |
| plugin | 5/5 | 5/5 | 5/5 |
| plugin-explicit | 5/5 | 5/5 | 5/5 |
| plugin-refs | 5/5 | 4/5 | 5/5 |

残った1件は、サービス名の問題です。
この実験のケースには、まだサービス名の一覧がありませんでした。

### 4.3 金額と質問の中身

金額は、すべての条件でほぼ同じでした。
static-site は、20回すべて 198.88 USD でした。
fargate-alb は、20回すべて 40.285〜40.29 USD でした。
missing-usage は、20回すべてが同じ6つの ID で質問しました。
金額を推測した回答は、ありませんでした。
参照資料の概算値（例：Serverless API は月 5〜20 USD）を使った回答も、ありませんでした。

### 4.4 道具の使われ方

| 条件 | スキルの呼び出し | 参照資料の読み取り | MCP 呼び出し |
|---|---|---|---|
| baseline | なし | なし | 0 |
| plugin | 0/15 | 0/15 | 65 |
| plugin-explicit | 15/15 | 0/15（15回とも拒否） | 59 |
| plugin-refs | 15/15 | 15/15 | 63 |

plugin 条件では、スキルが一度も自動で呼ばれませんでした。
MCP は使われました。
plugin-explicit では、スキルの参照資料の読み取りが15回とも拒否されました。
参照資料が workspace の外にあったためです。

awspricing の呼び出しは90回ありました。
90回すべてが「Unable to locate credentials」で失敗しました。
Agent は失敗のあと、awsknowledge で公式の料金ページを読みました。
その単価で計算しました。

missing-usage の1回では、使用量がないのに料金を3回照会しました。
答えには影響しませんでした。

### 4.5 費用と時間

表の値は、1試行あたりの平均です。
費用は Claude Code が表示した list 価格での概算です。

| 条件 | 費用（USD） | 時間（秒） |
|---|---|---|
| baseline | 0.12 | 35 |
| plugin | 0.33 | 53 |
| plugin-explicit | 0.40 | 58 |
| plugin-refs | 0.38 | 56 |

プラグインを使う条件は、費用が約2.7〜3.2倍でした。
時間は約1.5〜1.7倍でした。

### 4.6 根拠の質

static-site では、プラグインを使う3条件の15回すべてに、料金ページ以外の URL が入っていました。
例は、S3 Object Lock のブログ、QR コードメニューのブログ、`pm/tpf/pdp-template2/` です。
検索結果をそのまま根拠に並べたと考えられます。
baseline では、料金ページ以外の URL は0件でした。

### 4.7 LLM Judge

60回答すべてが意味品質の基準を満たしました。
重大な懸念は0件でした。
3回の判定の差は、最大で1点でした。
各次元の中央値は4〜5点でした。
actionability は、static-site と fargate-alb でプラグイン条件が5点、baseline が4点でした。
Judge は、4.6 の無関係な根拠を一度も指摘しませんでした。

## 5. 考察

### 5.1 正確さは上がらなかった

今回の3ケースでは、baseline がすでに全問正解でした。
そのため、プラグインで正確さが上がる余地がありませんでした。
モデルが主要サービスの単価を覚えていたと考えられます。
差を見るには、単価を覚えにくいケースが必要です。
例は、あまり使われないサービスや、最近価格が変わったサービスです。

### 5.2 情報不足のときの振る舞いは変わらなかった

スキルには「迷わせる質問をしない」という方針があります。
この方針で、推測が増えるおそれがありました。
しかし、20回すべてが推測せずに質問しました。
プロンプトの判断規則が、スキルの方針より強く効いたと考えられます。

### 5.3 スキルは自動では使われなかった

スキルの説明は「estimate AWS cost」などの英語の言い回しで起動します。
今回のプロンプトは日本語で、形式も細かく決めていました。
そのため、Agent がスキルを選ばなかったと考えられます。
プラグインを入れただけでは、スキルの知識が使われるとは限りません。

### 5.4 厳しい隔離ではスキルが半分しか働かない

読み取り専用で許可を聞かない設定では、参照資料を読めませんでした。
評価でスキルを測るには、プラグインのフォルダを読み取り許可に加える必要があります。
これは評価環境の設計上の注意点です。

### 5.5 価格 MCP は認証がないと使えない

awspricing は、AWS 認証がないとすべて失敗しました。
今回の結果は「価格 MCP が使えない状態のプラグイン」の評価です。
価格 MCP が働く状態の評価は、まだしていません。
awsknowledge は認証なしで料金ページを読めました。
これが失敗を補いました。

### 5.6 生のページを読むと、厳しすぎる oracle が目立つ

プラグイン条件は、最新の料金ページを読みました。
そのため、古い URL を完全一致で求める oracle に落ちました。
これはプラグインの誤りではありません。
oracle の作り方の問題です。
ワークショップのチェッカーは、下位ページを受け入れるよう直しました。

### 5.7 Judge は根拠の関連性を見ていない

Judge の rubric には「根拠が内容と関係あるか」という観点がありません。
そのため、無関係なブログが混ざっても高い点が付きました。
点がほぼ満点に集まり、条件の差を見分けにくい状態でした。
根拠の関連性は、URL のホストとパスを見る決定的ゲートにもできます。

### 5.8 まとめ

今回の条件では、deploy-on-aws は見積もりの正確さを上げませんでした。
費用は約3倍になりました。
時間は約1.6倍になりました。
根拠に無関係な URL が混ざりました。
一方で、最新の公式ページを読む力は上がりました。
価格が変わる場面では、この力が役に立つ可能性があります。

## 6. 限界

- ケースは3つだけです。
- 各条件の試行は5回だけです。区間は広いです。
- 価格 MCP は、認証がない状態でしか試していません。
- Agent は Claude Code の1モデルだけです。
- 回答の一部に「スキル」「deploy-on-aws」という語がありました。Judge の匿名化は完全ではありません。
- Judge の gold set による校正はしていません。「未校正」です。
- plugin-explicit と plugin-refs は、途中で足した条件です。
- plugin-explicit の最初の15回は、claude.ai の利用上限（HTTP 429）で回答前に失敗しました。理由を記録して退避し、上限が戻ってから測り直しました。
- 最初の Judge 90回は、Codex が git の外のフォルダで起動を拒否して失敗しました。`--skip-git-repo-check` を付けて測り直しました。

## 7. 次に変える一つの要因

次は、価格 MCP を使える状態にして測ります。
`pricing:*` だけを持つ短期 profile を用意します。
ケースには、単価を覚えにくいサービスを1つ加えます。
ほかの条件は、今回と同じにします。

## 付録：条件ごとの主な起動オプション

すべての条件に共通するオプションです。

```text
claude -p --model claude-opus-5-5 --max-turns 40
  --output-format stream-json --verbose
  --no-session-persistence --permission-mode dontAsk
  --settings '{"claudeMdExcludes":["**/AGENTS.md","**/CLAUDE.md"],"autoMemoryEnabled":false}'
  --strict-mcp-config --json-schema "<CLI用Schema>"
```

条件ごとに足したオプションです。

```text
baseline:        --mcp-config '{"mcpServers":{}}' --tools "Read,Glob,Grep"
plugin:          --plugin-dir <deploy-on-aws> --mcp-config <plugin-mcp.json>
                 --tools "Read,Glob,Grep,Skill"
                 --allowedTools "mcp__awsknowledge__*" "mcp__awsiac__*" "mcp__awspricing__*"
plugin-explicit: plugin と同じ。プロンプト先頭に「deploy-on-aws:deploy スキルの見積もり手順を使ってください。デプロイとIaC生成はしません。」
plugin-refs:     plugin-explicit と同じ。--add-dir <deploy-on-aws>
```

環境変数から AWS の認証情報を外しました。
`AWS_CONFIG_FILE` と `AWS_SHARED_CREDENTIALS_FILE` は、存在しないパスにしました。
