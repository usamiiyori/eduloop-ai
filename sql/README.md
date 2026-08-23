# sql/

Supabase (PostgreSQL) のスキーマ・RLSポリシーを置くディレクトリ。番号付きマイグレーションファイルとして追加する。既存ファイルは変更せず、変更は新しい番号のファイルを追記する（`CLAUDE.md` 第8章）。

- `0001_initial_schema.sql`: Phase 1 初期スキーマ。一次情報・書誌・生成物(drafts)・G1〜G6検証結果・監査ログ・収益KPI・教員コミュニティの全テーブルとRLSポリシー。Phase5でSupabaseプロジェクトに適用済み。
- `0002_l2_review_queue.sql`: Phase 5。Web承認画面用の`reviewers`テーブルと、承認/却下/修正指示を行う`l2_approve_draft`/`l2_reject_draft`/`l2_request_revision`関数（SECURITY DEFINER）。適用済み。
- `0003_phase6_operations.sql`: Phase 6。LLMコスト記録用の`llm_cost_log`と、キルスイッチ用の`system_control`。
