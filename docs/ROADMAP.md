# EduLoop AI — フェーズ計画と進捗

各Phase完了時に必ず停止し、`CLAUDE.md` 末尾の「Phase報告フォーマット」で報告してオーナーの承認を待つ（`CLAUDE.md` 第0章ルール1）。

## 現在地

**Phase 5 着手中・一時停止中（オーナーからのSupabaseプロジェクト作成待ち）。**
承認フローはSlack（オーナー選定）に決定。UTM・収益導線・note整形・X下書き・Web公開ロジックは
実装・テスト済みだが、実際の承認操作を行う「Web承認画面」本体はSupabaseの実プロジェクトが
ないと実装・検証できないためブロック中。取得手順は `docs/運用マニュアル.md` 参照。

## 解決済みの判断事項

- `make` コマンドはWindowsに標準で入っていないため、`docs/運用マニュアル.md` に `winget install GnuWin32.Make` での導入手順を明記した（オーナー承認済み）。
- 本番シークレットは GitHub Actions Secrets を使用する（Google Secret Managerは使わない、オーナー承認済み）。

## Phase 0 — 基盤と憲法

- [x] リポジトリ構造: `src/scrapers/` `src/processors/` `src/harness/` `src/publishers/` `src/models/` `config/` `tests/` `docs/`
- [x] `CLAUDE.md` の作成: アーキテクチャ原則、コーディング規約、テスト方針、「オーナーは非エンジニアである」という前提、禁止事項を明文化
- [x] `pyproject.toml`、`.gitignore`、`.env.example`、`Makefile`（コマンド枠だけ）
- [x] `docs/運用マニュアル.md` の骨子
- → 停止・報告

## Phase 1 — データモデルとDB

- [x] Pydantic v2 モデル（一次情報、SIST02書誌、記事、Xスレッド、YouTube台本、検証結果、メトリクス）
- [x] Supabase スキーマSQL + RLSポリシー（将来の教員コミュニティ機能を見越したテーブル設計を含む）
- [x] `config/sources.yaml` のスキーマとライセンス台帳の初期定義（21ソース。大半は`license: unconfirmed`の暫定値）
- → 停止・報告済み（スキーマ図を日本語で図解）

## Phase 2 — 収集層

- [x] RSS / HTML差分 / PDF に対応した汎用クローラー基盤
- [x] `config/sources.yaml` から動的にソースを読み込む仕組み
- [x] `source_health` 記録（インメモリ実装。Supabase接続後に永続化実装へ差し替え予定）、robots.txt 尊重、レート制限
- → 停止・報告済み（4ソースから実データ86件取得、0エラー）

## Phase 3 — ハーネス層

- [x] G1〜G6 の6ゲート実装（G1文字列/あいまい一致・G4断定リスクは規則ベースの暫定実装。
      LLM-as-a-Judgeへの置き換えはGOOGLE_GENAI_API_KEY設定後のPhase4/6で対応）
- [x] 自己修復ループ（最大3回リトライ、3回失敗でneeds_human）
- → 停止・報告済み（意図的に誤りを含む5パターンで各ゲートのブロックを実演、自己修復ループも実演）

## Phase 4 — 生成層

- [x] 論点抽出（Fact / Implication / Discussion / Citation）… Gemini(gemini-2.5-flash)で実行確認済み
- [x] コンテキスト層（編集ペルソナ実装済み。過去出力/自治体方針/教員フィードバックは
      Supabase未接続のため空リスト。Phase6でデータ源を接続）
- [x] Web記事Markdown / Xスレッド / YouTube台本 の3形式生成 … 実データで生成確認済み
- [x] ネタ選定スコアリング（score_impact×score_timeliness×score_controversy、
      閾値27は暫定値、`ARTICLE_SCORE_THRESHOLD`で調整可能。実サンプルはscore_total=100）
- [x] **実在の一次情報（文科省 生成AI利活用ガイドラインVer.2.0概要PDF）から3形式の実サンプルを
      生成し、harness(G1〜G6)で検証**
- [x] G1事実整合性ゲートをGemini埋め込み(gemini-embedding-001)による意味的類似度判定に
      アップグレード（文字列一致→あいまい一致→埋め込み判定の3段構成。埋め込み未設定時は
      従来のフェイルクローズ動作を維持）
- → 停止・報告済み

## Phase 5 — 承認と配信

- [x] 承認フロー（Discordではなく**Slack**に決定。オーナーが普段Discordを使わないため。
      Slackは「レビュー依頼」通知専用、実際の承認操作はWeb承認画面で行うハイブリッド方式）
- [x] UTM自動付与（`src/publishers/utm.py`）
- [x] 収益導線テンプレート（note有料版導線・問い合わせ導線を記事末尾に自動挿入）
- [x] note下書き出力（見出し・区切り形式に整形、コピペ用）
- [x] X投稿（draft/api切替。draftのみ実装。apiは2026年のX API従量課金化を確認した上で
      Phase6に先送り、実装前にオーナーの課金設定確認が必要なため）
- [x] Web記事「公開」ロジック（承認済み(approved)以外は例外で拒否。実際のDB永続化は
      Supabase接続後に差し替え可能な設計）
- [ ] **Web承認画面本体**（Supabaseプロジェクト未作成のためブロック中。下記参照）
- → オーナーからのSupabaseプロジェクト作成後に画面実装・報告を完了する

## Phase 6 — 自動運用と計測

- [ ] GitHub Actions cron（L1毎時 / L2日次 / L3月次）
- [ ] `make doctor` / `make cost` / `make stop`
- [ ] メトリクス収集と月次レポート
- [ ] 運用マニュアル完成
- → 完了報告

## 未確認事項（実装前に公式ドキュメント確認が必要）

- X API の書き込み料金は確認済み（2026-08-22）: 新規開発者向け無料枠は廃止され、
  投稿$0.015/件・リンク付き$0.20/件の従量課金制。オーナーが費用発生を避けたいとの意向を
  示したため、`X_PUBLISH_MODE=draft`（手動投稿・無料）を既定のまま維持する方針で確定。
  api モードの実装は見送り（要望があれば再検討）
- note の投稿API有無（現時点は非公開API前提。Phase 5 着手前に再確認）
- Slack Incoming Webhook は送信専用で、ボタン操作の受信にはInteractivity機能＋常時稼働
  サーバーが必要と確認済み（2026-08-22）。そのため承認操作はWeb承認画面に分離した
- `config/sources.yaml` のうち `license: unconfirmed` の残り19ソースの利用規約未確認
  （Phase 2でMEXT分は実URL疎通確認・修正済み。それ以外は個別の利用規約ページ未確認のまま）
- `SCRAPER_CONTACT_URL`（User-Agentに載せる連絡先）が未設定。本番運用前に設定必須
- G1（事実整合性）はGemini埋め込みによる意味的判定を追加済み（Phase4）。閾値0.80は暫定値で
  実運用しながらの較正が必要（実サンプルでXスレッドの1文が0.79で境界ブロックされた実績あり）
- G5（重複判定）はまだdifflib文字列類似度の暫定実装のまま。G1同様の埋め込みアップグレードは
  Phase6で対応する
- G4（断定リスク）はキーワードベースの規則判定のまま。LLM-as-a-Judgeによる意味理解への
  置き換えはPhase6で対応する。現状は「検討中/審議中」等の語がある原文に対する強い断定表現
  のみ検出でき、それ以外の巧妙な誤読は見逃す可能性がある
- G3（PII）はメール・電話番号の正規表現＋固定ブロックリストのみ。日本語人名の一般検出は
  モデレーションAPI導入まで未対応（生徒名等は都度ブロックリストに追加する運用が必要）
- Gemini APIキーが新形式（`AQ.`プレフィックス）で発行された。google-genai SDK
  (2.18.1)・実際のAPI呼び出しでは問題なく動作することを確認済み
