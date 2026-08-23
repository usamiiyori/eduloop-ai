# config/

オーナーがコードを触らずに調整できる設定ファイルを置くディレクトリ。

- `sources.yaml`: 収集ソースのレジストリ + ライセンス台帳。1ソース = YAML1エントリで追加できる（`CLAUDE.md` 第4章、`docs/ARCHITECTURE.md` 第5章）。Phase 1時点では大半のソースが `license: unconfirmed` の暫定値。Phase 2着手前に1件ずつ公式利用規約ページを確認し更新すること。
- `editorial_voice.yaml`（Phase 4 で追加）: 編集ペルソナ・文体規定（`CLAUDE.md` 第5章、`docs/ARCHITECTURE.md` 第6章）。
