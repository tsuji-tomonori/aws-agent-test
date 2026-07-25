# 実験記録テンプレート

## 目的

- 仮説:
- 比較対象:
- 業務上の誤りコスト:

## 固定条件

| 項目 | 値 |
|---|---|
| dataset ID/version | |
| Agent CLI/version | |
| model/version | |
| Plugin/version or commit | |
| profile digest | |
| prompt digest | |
| asset lock digest | |
| repetitions | |
| region/currency | |
| 価格取得モード | frozen / public / Pricing MCP |
| AWS認証利用 | none / pricing-only |
| 実行日 | |

## 事前合格条件

- [ ] critical failure の定義を変更していない
- [ ] oracle が独立レビュー済み
- [ ] hidden oracle / cost page が Agent workspace に含まれていない
- [ ] 標準経路では AWS 認証情報を設定していない
- [ ] Pricing MCP を選んだ場合だけ、live 認証情報が pricing-only である
- [ ] public asset を使う場合は digest lock を保存した
- [ ] pilot で出力形式と費用を確認済み
- [ ] Judge を使う場合は gold set で校正済み

## 結果

- trial success rate / Wilson CI:
- pass@k:
- pass^k:
- 平均 score:
- 平均 latency:
- 推論費用:
- failure taxonomy:

## 解釈

- 仮説は支持されたか:
- 1回成功と反復成功の差:
- データ問題 / prompt 問題 / tool 問題 / model 問題の切り分け:
- 業務導入時に人間レビューが必要な箇所:

## 次のアクション

- [ ]
