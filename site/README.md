# AWS Agent Evaluation Workshop

Astro Starlightで作成した、`aws-agent-test`の実践型ハンズオンです。

公開サイト: https://tsuji-tomonori.github.io/aws-agent-test/

```bash
npm install
npm run dev
```

GitHub Pages向けの`site`と`base`は`astro.config.mjs`に設定しています。`main`へ反映されると`.github/workflows/deploy-workshop.yml`が静的サイトを公開します。

教材のファイル本文は`src/snippets/`を正本とし、MDXから`?raw`で読み込んで`FileCreate`へ渡します。保存先と形式を指定すると、作成コマンド・Vim手順・本文・確認コマンドを同じ内容から生成します。すべてのコードブロックは`Command`で囲み、3色の丸とコピーUIを統一してください。

コピー時にheredoc内のMarkdown見出しを失わないよう、Expressive Codeのコメント削除・ファイル名自動抽出は無効化しています。

リポジトリ直下での検証:

```bash
source .venv/bin/activate
pytest tests/test_workshop.py
cd site
npm ci
npm run build
cd ..
python site/scripts/check_rendered.py
```

pytestは実際の教材のBashを外部通信しないCLIスタブで実行し、両CLIの反復・判定・Judge・集計と失敗処理を検査します。描画検査は全コードブロックの共通コンポーネント使用と、コピーされるコマンドによるファイル内容の一致を確認します。ライブモデルやAWS認証は使用しません。
