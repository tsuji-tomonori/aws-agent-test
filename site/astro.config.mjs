import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://tsuji-tomonori.github.io',
  base: '/aws-agent-test',
  integrations: [
    starlight({
      title: 'AWS Agent Evaluation Workshop',
      description: 'LLMエージェントを一度の成功で判断しないための、実践型評価ハンズオン',
      defaultLocale: 'root',
      locales: {
        root: { label: '日本語', lang: 'ja' },
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/tsuji-tomonori/aws-agent-test' },
      ],
      editLink: {
        baseUrl: 'https://github.com/tsuji-tomonori/aws-agent-test/edit/main/site/',
      },
      customCss: ['./src/styles/custom.css'],
      expressiveCode: {
        frames: {
          // Heredocs contain Markdown headings and script comments: copy them verbatim.
          removeCommentsWhenCopyingTerminalFrames: false,
          extractFileNameFromCode: false,
        },
      },
      sidebar: [
        { label: 'はじめに', items: [
          { label: 'Workshop Home', link: '/' },
          { label: '0. 環境を準備する', slug: '00-getting-started' },
        ]},
        { label: '設計編', items: [
          { label: '1. 合否条件を設計する', slug: '01-evaluation-system' },
          { label: '2. テストケースを作る', slug: '02-mock-run' },
          { label: '3. プロンプトと出力を作る', slug: '03-dataset-design' },
        ]},
        { label: '実験編', items: [
          { label: '4. MCPを設定する', slug: '04-agent-profile' },
          { label: '5. 1ケースを実行・採点する', slug: '05-repeated-experiment' },
          { label: '6. 独立試行を繰り返す', slug: '06-llm-judge' },
        ]},
        { label: '実践編', items: [
          { label: '7. LLM Judgeを作る', slug: '07-live-pilot' },
          { label: '8. 比較実験を完成させる', slug: '08-capstone' },
        ]},
        { label: '付録', items: [
          { label: '成果物チェックリスト', slug: 'reference/commands' },
        ]},
      ],
      pagination: true,
      lastUpdated: true,
    }),
  ],
});
