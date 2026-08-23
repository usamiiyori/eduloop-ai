# .github/workflows/

GitHub Actions cron ワークフローを置くディレクトリ（`docs/ARCHITECTURE.md` 第3章）。

- `pages.yml`: `web/review/` をGitHub Pagesへ自動デプロイ（Phase 5）。
- `l1_collect.yml`: 収集〜生成〜検証。`SCRAPER_CONTACT_URL`未確定のため毎時cronは未有効化、`workflow_dispatch`の手動実行のみ（Phase 6）。
- `l2_publish.yml`: 承認済み記事の配信。日次cron（毎日 UTC 21:00 = JST 翌6:00）（Phase 6）。
- `l3_insights.yml`: 月次知見還元レポート。月次cron（毎月1日 UTC 21:00）（Phase 6）。
- `review_digest.yml`: レビュー依頼まとめメール。日次cron（毎日 UTC 9:00 = JST 18:00）（Phase 6、2026-08-23追加。SlackからGmail通知への移行に伴い、L1の即時通知に代わって導入）。

いずれも GitHub リポジトリの Settings → Secrets and variables → Actions に登録した値を `env:` 経由で渡す。ローカルの `.env` の値と対応させること。
