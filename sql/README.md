# sql/

Supabase (PostgreSQL) のスキーマ・RLSポリシーを置くディレクトリ。番号付きマイグレーションファイルとして追加する。既存ファイルは変更せず、変更は新しい番号のファイルを追記する（`CLAUDE.md` 第8章）。

- `0001_initial_schema.sql`: Phase 1 初期スキーマ。一次情報・書誌・生成物(drafts)・G1〜G6検証結果・監査ログ・収益KPI・教員コミュニティの全テーブルとRLSポリシー。まだ Supabase プロジェクトには未適用（Phase 2以降、`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` 設定後にオーナーの承認を得て適用する）。
