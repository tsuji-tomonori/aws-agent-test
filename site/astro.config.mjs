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
      sidebar: [
        { label: 'はじめに', items: [
          { label: 'Workshop Home', link: '/' },
          { label: '0. 環境を準備する', slug: '00-getting-started' },
        ]},
        { label: '基礎編', items: [
          { label: '1. 評価対象を定義する', slug: '01-evaluation-system' },
          { label: '2. Mockで配線を試す', slug: '02-mock-run' },
          { label: '3. ケースを設計する', slug: '03-dataset-design' },
        ]},
        { label: '実験編', items: [
          { label: '4. Profileを読み解く', slug: '04-agent-profile' },
          { label: '5. 反復実験を評価する', slug: '05-repeated-experiment' },
          { label: '6. LLM Judgeを校正する', slug: '06-llm-judge' },
        ]},
        { label: '実践編', items: [
          { label: '7. Live pilotを安全に行う', slug: '07-live-pilot' },
          { label: '8. 評価計画を完成させる', slug: '08-capstone' },
        ]},
        { label: '付録', items: [
          { label: 'コマンド早見表', slug: 'reference/commands' },
        ]},
      ],
      pagination: true,
      lastUpdated: true,
    }),
  ],
});
