# AWS Agent Plugins 評価レポート（第2回）

実施日：2026-09-28
本試行は 00:39〜00:55 JST に実施しました。

## 1. 目的

AWS Agent Plugins の deploy-on-aws プラグインを評価しました。
[前回のレポート](2026-09-25-aws-agent-plugins-evaluation.md)の §5.1 を検証します。
意図して変えた要因は、ケースの組み合わせです。
比較用の static-site を残し、あまり使われないサービスのケースを加えました。

仮説 H1 は、試行前に登録しました。
「新規2ケースを合わせた合格率は、plugin-refs が baseline より高い」です。
比較用のケースは、この仮説の集計から外します。

## 2. 実験の条件

### 2.1 固定したもの

- Agent：Claude Code 2.1.283
- モデル：claude-opus-5-5
- プラグイン：deploy-on-aws 1.3.0、コミット `097fe8ad56d8a1d5e2c81d7880adf145553cf244`
- MCP：aws-iac-mcp-server 1.0.26、aws-pricing-mcp-server 1.1.1、awsknowledge
- プロンプト：前回と同じ agent-v1
- 出力 Schema：前回と同じ CLI 用 Schema
- チェッカー：前回の修正後の check_result.py を変更せず使用
- 反復：各条件・各ケースで5回、毎回新しい workspace と会話を使用
- 隔離：AGENTS.md、CLAUDE.md、自動記憶を読み込まない
- AWS 認証：環境変数から外し、認証ファイルとメタデータ経由の取得も無効化
- 道具：Read、Glob、Grep。プラグイン条件では Skill と同梱 MCP も使用可能

前回の CLI は 2.1.282 でした。
今回の 2.1.283 への差は、意図した要因以外の環境差です。
awsknowledge は URL を固定しましたが、遠隔サービスの実装版は固定できていません。

### 2.2 比べた条件

| 条件 | 内容 |
|---|---|
| baseline | プラグインなし。MCP なし |
| plugin | プラグインと同梱 MCP を使用可能。スキルを使うかは Agent に任せる |
| plugin-refs | plugin にスキルを使う指示と、参照資料フォルダの読み取り許可を追加 |

前回の plugin-explicit は省きました。
plugin-refs との違いが、参照資料の読み取り拒否だけだったためです。

### 2.3 ケース

すべて us-east-1 の公開オンデマンド料金で計算します。
無料枠、割引、税は除きます。
oracle は採点用の正解値です。

| ケース | 役割と確認する内容 | 正解月額（USD） | 合格範囲（USD） |
|---|---|---:|---:|
| cfn-static-site | 前回から残す比較用。S3 と CloudFront の保存・リクエスト・転送 | 198.88 | 196.83〜200.93 |
| cfn-kvs-webrtc | 新規。WebRTC のチャネル、シグナリング、TURN の単価 | 8.94 | 8.85〜9.03 |
| cfn-iot-core | 新規。接続、メッセージ、Registry／Shadow 操作の単価 | 60.006912 | 59.40〜60.61 |

入力には、課金単位に換算済みの使用量を与えました。
利用しない機能や通信の範囲も明記しました。
利用状況から課金量を求める部分は、今回の課題に含めていません。

### 2.4 oracle の作り方と価格履歴の探索

新規ケースの単価は、版を固定した AWS Price List の offer ファイルから取りました。
AmazonKinesisVideo は `20260911134126`、AWSIoT は `20260911124556` です。
取得ファイルの SHA-256、SKU、単位、数量、単価、計算結果を保存しました。
計算には Python の Decimal を使いました。
合格範囲は正解値の99%をセント単位で切り下げ、101%を切り上げています。
比較用の static-site は、前回の正解値と合格範囲を維持しました。

監督の Claude は、試行前に同じ版を独立に再取得しました。
単価と計算を再確認し、両方の oracle が一致しました。
このレビューは SUPERVISOR-REVIEW.md に記録しています。

価格履歴は、Transfer Family、Kinesis Video Streams、IoT に範囲を絞って調べました。
2025-06-01 以降の版と、その直前の版を対象にしました。
us-east-1 の19ファイルで、共通する SKU と rateCode の価格を比較しました。

KVS の保存フラグメントでは、数値欄が 0.01 USD から 0.00001 USD に変わっていました。
しかし、旧版の説明には「1,000フラグメントあたり 0.01 USD」とありました。
単位の表現を直した可能性があるため、実際の値下げとは判断しませんでした。
この変更はケースに使っていません。
探索した範囲では、採用した単価に変化を確認できませんでした。
AWS 全体で価格変更がなかったことを示す結果ではありません。

### 2.5 採点

決定的ゲートは、変更していない check_result.py です。
副指標も、試行前に登録しました。
副指標 (a) は、課金項目ごとの単価の一致です。
単位をそろえ、正解との相対誤差が0.5%以内なら一致とします。
名前や数量から課金項目を一意に対応づけられない場合は、未判定にします。
副指標 (b) は、根拠 URL のホストとパスによる関連性です。
どちらも主指標の合否は変えません。

LLM Judge は使いませんでした。
前回は点がほぼ満点に集まり、無関係な根拠も見逃したためです。
今回は、根拠 URL を決定的な規則で数えます。

## 3. 実施体制

実験の操作は Codex CLI が担当しました。
監督の Claude が各段階をレビューしました。
本試行前に各条件で1回ずつ、計3回の pilot を行いました。
pilot は、本試行45回の集計から外しています。
本試行の無効な環境失敗と再試行は0件でした。

記録された呼び出しを監査しました。
oracle などの採点資料へのアクセスを疑う記録は0件でした。
書き込みを伴う可能性がある MCP 呼び出しの検出も0件でした。
監査対象は、ストリームに残った呼び出しです。

監督は、本試行45回答のチェッカーを独立に再実行しました。
生のストリームから集計も再計算し、results/summary.* との一致を確認しました。
本レポートの作成では、既存成果物とローカル分析だけを使いました。

## 4. 結果

### 4.1 決定的ゲート（事前に決めた規則）

| 条件 | static-site | kvs-webrtc | iot-core |
|---|---:|---:|---:|
| baseline | 5/5 | 5/5 | 5/5 |
| plugin | 5/5 | 5/5 | 5/5 |
| plugin-refs | 5/5 | 5/5 | 5/5 |

全45回答が合格しました。
各セルの Wilson 95% 区間は 0.57〜1.00 です。

### 4.2 H1：新規ケースを合わせた比較

| 条件 | 新規ケースの合格数 | Wilson 95% 区間 |
|---|---:|---:|
| baseline | 10/10 | 0.72〜1.00 |
| plugin | 10/10 | 0.72〜1.00 |
| plugin-refs | 10/10 | 0.72〜1.00 |

plugin-refs と baseline の合格率の差は0ポイントでした。
H1 が予測した優位は観測されませんでした。
条件が同等だと証明した結果ではありません。

### 4.3 金額と単価（副指標 a）

| ケース | 全条件での回答月額（USD） | 一致した回答 |
|---|---:|---:|
| static-site | 198.88 | 15/15 |
| kvs-webrtc | 8.94 | 15/15 |
| iot-core | 60.006912 | 15/15 |

新規ケースでは、次の単価を全条件で再現しました。

| ケース | 課金項目 | 単価（USD） |
|---|---|---:|
| kvs-webrtc | アクティブなチャネル | 0.03／チャネル月 |
| kvs-webrtc | シグナリングメッセージ | 2.25／100万件 |
| kvs-webrtc | TURN | 0.12／1,000分 |
| iot-core | 接続 | 0.08／100万分 |
| iot-core | pub/sub メッセージ | 1.00／100万件 |
| iot-core | Registry／Shadow 操作 | 1.25／100万件 |

| 条件 | 新規ケース：一致／対象項目 | static-site：一致／対象項目 | static-site：未判定 |
|---|---:|---:|---:|
| baseline | 30/30 | 19/25 | 6 |
| plugin | 30/30 | 15/25 | 10 |
| plugin-refs | 30/30 | 15/25 | 10 |

新規ケースは合計90/90項目が一致しました。
static-site は49/75項目が一致し、26項目が未判定でした。
判定できた項目の単価不一致は0件でした。

未判定は、S3 の PUT と GET の行です。
たとえば「S3 Standard PUT/COPY/POST/LIST requests」は、保存とリクエストの名前の規則に同時に一致しました。
回答に単価があっても、対応規則が課金項目を選べませんでした。
これは副指標の対応規則の限界です。
Agent の単価誤りとしては数えていません。

KVS には、使用量ゼロの機能を補足した未対応の行も7件ありました。
これらは、採点対象の3項目を置き換えていません。

### 4.4 道具の使われ方

| 条件 | Skill を使った試行 | 参照資料を読んだ試行 | awspricing | awsknowledge | awsiac |
|---|---:|---:|---:|---:|---:|
| baseline | 0/15 | 0/15 | 0 | 0 | 0 |
| plugin | 0/15 | 0/15 | 32 | 36 | 0 |
| plugin-refs | 15/15 | 15/15 | 31 | 38 | 0 |

MCP の列は呼び出し回数です。
awspricing は63回すべてが「Unable to locate credentials」で失敗しました。
awsknowledge は74回呼ばれ、記録されたエラー結果は0件でした。
内訳は read_documentation が49回、search_documentation が25回です。

baseline の外部価格照会は0回でした。
入力ファイルの Read や Glob は使っています。
単価は外部の道具で取得せずに再現しました。

### 4.5 費用と時間

表の値は、各条件の全15試行の平均です。
費用は Claude Code が表示した list 価格での概算です。
AWS の見積もり月額とは別です。
時間は各試行の開始から終了までの実測秒数です。
倍率は、丸める前の平均から計算しました。

| 条件 | 費用（USD） | baseline 比 | 時間（秒） | baseline 比 |
|---|---:|---:|---:|---:|
| baseline | 0.1033 | 1.00 | 27.3 | 1.00 |
| plugin | 0.3289 | 3.18 | 43.5 | 1.59 |
| plugin-refs | 0.3934 | 3.81 | 49.1 | 1.80 |

全45試行の CLI 費用は、合計 12.383390 USD でした。

### 4.6 根拠の関連性（副指標 b）

関連ありとするのは、次のホストとパスです。
`aws.amazon.com` でパスに `/pricing` を含む URL、`pricing.us-east-1.amazonaws.com`、`calculator.aws` です。
以下では、それ以外を「基準外 URL」と呼びます。
URL は回答の sources に現れた件数で数えます。

| 条件 | 基準外 URL を含む試行 | 基準外 URL／全 URL | URL なしの試行 |
|---|---:|---:|---:|
| baseline | 0/15 | 0/20 | 0/15 |
| plugin | 5/15 | 7/27 | 0/15 |
| plugin-refs | 6/15 | 10/31 | 0/15 |

合計では11試行に、延べ17件の基準外 URL がありました。

実際に含まれていた URL は次のとおりです。

| URL | 延べ件数 |
|---|---:|
| [S3 レプリケーションの転送費用](https://aws.amazon.com/blogs/storage/monitor-data-transfer-costs-related-to-amazon-s3-replication/) | 3 |
| [pdp-template2](https://aws.amazon.com/pm/tpf/pdp-template2/) | 1 |
| [ライブ配信の費用例 2](https://docs.aws.amazon.com/solutions/latest/live-streaming-on-aws-with-amazon-s3/cost-example-2.html) | 5 |
| [QR コードの飲食店メニュー](https://aws.amazon.com/blogs/industries/hosting-qr-code-restaurant-menus-on-amazon-s3/) | 3 |
| [Connected Mobility の導入計画](https://docs.aws.amazon.com/guidance/latest/connected-mobility-on-aws/plan-your-deployment.html) | 2 |
| [ライブ配信の費用例 1](https://docs.aws.amazon.com/solutions/latest/live-streaming-on-aws-with-amazon-s3/cost-example-1.html) | 2 |
| [S3 の保存期間の一括管理](https://aws.amazon.com/blogs/storage/how-to-manage-retention-periods-in-bulk-using-amazon-s3-batch-operations/) | 1 |

QR コードメニューやライブ配信など、対象ケースとは違う用途の URL が混ざりました。
ただし、この規則は URL の形式だけを見ています。
基準外の文書がすべて意味的に無関係だと判定したわけではありません。

### 4.7 前回との比較（static-site）

| 条件 | 今回の合格数 | 今回の回答月額（USD） |
|---|---:|---:|
| baseline | 5/5 | 198.88 |
| plugin | 5/5 | 198.88 |
| plugin-refs | 5/5 | 198.88 |

前回も、回答月額はすべて 198.88 USD でした。
前回の当初の判定では、URL の照合が厳しすぎる問題がありました。
修正後の再採点でも、plugin-refs にサービス名による不合格が残りました。
今回は、どの条件にも不合格はありませんでした。
CLI と遠隔 MCP の環境差もあるため、改善効果とは判断しません。

## 5. 考察

### 5.1 あまり使われないサービスでも差は出なかった

H1 は支持されませんでした。
baseline は新規ケース10/10回に合格し、単価も30/30項目を再現しました。
外部価格照会は0回でした。
モデルが記憶している単価で解けたと考えられます。
この説明は、前回の §5.1 から、今回のあまり使われないサービスにも広がります。
サービスの知名度を下げるだけでは、正確さに差が出ませんでした。
探索範囲で変化のない、長く安定した単価は、今回のモデルを比べる課題として弱かったと考えられます。

### 5.2 課金量を与えたことで課題が易しくなった

新規ケースは全条件で30/30回合格しました。
入力には、すでに課金単位へ換算した数量がありました。
Agent は、単価の選択と掛け算を中心に解けました。
メッセージのサイズや通信経路から課金量を求める難しさを省いています。
これは、今回の設計上の限界です。

### 5.3 スキルは今回も自動では使われなかった

plugin の Skill 呼び出しは0/15回でした。
前回の §5.3 と同じ結果です。
明示した plugin-refs では15/15回使われました。
しかし、どちらの条件も15/15回合格しました。
スキルの使用は増えましたが、正確さの上積みは見られませんでした。

### 5.4 正確さの上積みなしに費用と時間が増えた

plugin は、費用が約3.2倍、時間が約1.6倍でした。
plugin-refs は、費用が約3.8倍、時間が約1.8倍でした。
全条件が15/15回合格したため、この増加に対応する正確さの向上はありませんでした。

### 5.5 基準外 URL は検索を使った試行に集中した

検索と基準外 URL の有無を、試行ごとに照合しました。
検索は `aws___search_documentation` の呼び出しを指します。

| 条件 | 検索あり・基準外あり | 検索あり・基準外なし | 検索なし・基準外あり | 検索なし・基準外なし |
|---|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 15 |
| plugin | 5 | 1 | 0 | 9 |
| plugin-refs | 6 | 1 | 0 | 8 |
| 合計 | 11 | 2 | 0 | 32 |

基準外 URL を含む11試行は、すべて検索を呼び出していました。
検索した13試行のうち、2試行は基準外 URL を含みませんでした。
両者は完全には一致しません。
検索した試行で基準外 URL が混ざる傾向は見られます。
検索の有無は無作為に割り当てていないため、検索が原因だとは断定できません。

### 5.6 認証がある価格 MCP は未評価のまま

awspricing は63/63回が認証不足で失敗しました。
その状態でも、全45回答が合格しました。
今回測ったのは、価格 MCP を使えない状態のプラグインです。
認証がある状態での正確さ、費用、時間は、まだ分かりません。

### 5.7 まとめ

あまり使われないサービスに替えても、baseline は全問正解でした。
プラグインは、正確さを上げずに費用と時間を増やしました。
検索を使った試行には、基準外 URL が混ざりました。
次は、記憶した単価では正解できないケースが必要です。

## 6. 限界

- 各条件・各ケースは5回だけで、区間は広いです。
- Agent は Claude Code の単一モデルです。
- CLI は前回の 2.1.282 から 2.1.283 に変わっています。
- 遠隔の awsknowledge は実装版を固定できていません。
- 実際の価格変更が確認できたケースはありません。
- 課金量、対象範囲、除外項目を入力に明記しています。
- 副指標 (a) は、S3 の26項目を対応規則のため判定できませんでした。
- 副指標 (b) は URL の形式だけを見ます。
  ページが単価を裏づけるかは検証しません。
- LLM Judge を使っていないため、説明全体の意味品質は採点していません。
- 価格 MCP は認証がない状態でしか試していません。
- 今回のケースは、単価と総額を公開した参照ケースです。
  今後の隠した正解で測る実験では、公開済みとして扱う必要があります。

## 7. 次に変える一つの要因

次は、正解の単価と、モデルが思い出しやすい単価が異なるケースに替えます。
変える要因は、引き続きケースの組み合わせだけにします。
最近の価格変更を一次資料で確認できるケースを優先します。
該当例がなければ、一般的な単価が当てはまらないリージョン、階層、SKU を候補にします。
モデル、プロンプト、道具、認証の条件は維持します。

理由は、今回の baseline が新規ケース10/10回、単価30/30項目で正解したためです。
記憶した単価で解けるままでは、ほかを変えても正確さの上限に達した状態が続きます。
候補の選定規則と正解値を、試行前に固定します。
`pricing:*` だけを持つ profile の導入は、別の実験候補です。
今回は、それを次の変更と同時には行いません。

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
baseline:    --mcp-config '{"mcpServers":{}}' --tools "Read,Glob,Grep"
plugin:      --plugin-dir <deploy-on-aws> --mcp-config <plugin-mcp.json>
             --tools "Read,Glob,Grep,Skill"
             --allowedTools "mcp__awsknowledge__*" "mcp__awsiac__*" "mcp__awspricing__*"
plugin-refs: plugin と同じ。--add-dir <deploy-on-aws>
             プロンプト先頭に「deploy-on-aws:deploy スキルの見積もり手順を使ってください。デプロイとIaC生成はしません。」
```

環境変数から AWS の認証情報と代替認証プロバイダーを外しました。
`AWS_CONFIG_FILE` と `AWS_SHARED_CREDENTIALS_FILE` は、存在しないパスにしました。
`AWS_EC2_METADATA_DISABLED=true` を指定しました。

## 付録：確認に使う成果物

パスは、この実験ディレクトリからの相対パスです。
実験ディレクトリは実施者の手元にあり、リポジトリには含めていません。
AGENTS.md の方針どおり、生成物と取得した offer ファイルはコミットしません。
数値と出典の対応は REPORT-numbers.json に記録しています。

| 成果物 | 確認できる内容 |
|---|---|
| `experiment.json` | 条件、H1、副指標、事前登録 |
| `results/summary.json`、`results/summary.md` | 合否、区間、単価、費用、時間、道具、URL |
| `results/audit.json` | 記録されたファイルアクセスと MCP の監査 |
| `results/<条件>/<ケース>/trial-*/stream.jsonl` | 生の出力、CLI・モデル情報、呼び出しとエラー |
| 同じ試行ディレクトリの `answer.json`、`verdict.json` | 回答とチェッカー判定 |
| 同じ試行ディレクトリの `metrics.json`、`seconds.txt`、`validity.json` | 費用、時間、ターン、道具、有効性 |
| `cases/<ケース>/case-public.json`、`input/template.yaml`、`oracle.json` | 入力と主指標の正解 |
| 新規ケースの `oracle-derivation.json` | 固定版、ハッシュ、単価、計算、価格履歴の探索 |
| `offers/`、`validation/price-history-search.json` | 保存済み offer ファイルと価格履歴の比較 |
| `analysis-reference.json`、`aggregate.py` | 副指標の基準と集計規則 |
| `materials/prompts/agent-v1.md`、`materials/schemas/agent-output.schema.json`、`materials/scripts/check_result.py` | 固定したプロンプト、Schema、チェッカー |
| `run_trial.sh`、`plugin-mcp.json` | 起動オプションと MCP 設定 |
| `results/schedule.json`、`results/execution.jsonl` | 実施順と時刻 |
| `pilot/results/` | 集計から除外した pilot |
| `SUPERVISOR-REVIEW.md` | oracle と本試行集計の独立レビュー |
| `REPORT-numbers.json` | 数値の出典、平均と倍率の計算、検索と URL の試行別対応 |
