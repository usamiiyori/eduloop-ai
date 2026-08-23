# EduLoop AI

教育・生成AI 公的情報自律配信＆知見集約プラットフォーム。公的機関・学術機関の一次情報を自律収集・検証し、教育現場向けに配信、教員コミュニティの実践知を循環させる Human-on-the-Loop 型システム。

- 設計思想・4層アーキテクチャ・収集ソース一覧: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 開発規約・ディレクトリ責務・禁止事項: [`CLAUDE.md`](CLAUDE.md)
- フェーズ計画・進捗: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- 運用マニュアル（非エンジニア向け）: [`docs/運用マニュアル.md`](docs/運用マニュアル.md)

## セットアップ

```bash
make setup   # venv作成・依存インストール・.env雛形コピー
```

内部的には以下と同等（`make setup` が使えない環境向け）:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env  # 値を各自設定（コミット禁止）
```

## よく使うコマンド

```bash
make run     # 収集〜検証〜配信パイプラインを実行
make doctor  # 接続・設定の診断（日本語）
make test    # pytest + ruff + mypy
make cost    # 当月のLLM API推定コスト
make stop    # キルスイッチ（全自動処理を停止）
```

## 現在の進捗

詳細は [`docs/ROADMAP.md`](docs/ROADMAP.md) を参照。

- [x] Phase 0: プロジェクト基盤・CLAUDE.md・設計ドキュメント・Makefile枠
- [x] Phase 1: データモデル・Supabaseスキーマ・sources.yaml
- [x] Phase 2: 収集層（スクレイパー基盤）
- [x] Phase 3: ハーネス層（G1〜G6）
- [x] Phase 4: 生成層（実データで生成・検証済み）
- [~] Phase 5: 承認と配信（Slack通知・UTM・note整形・X下書きは完成。Web承認画面はSupabase待ち）
- [ ] Phase 6: 自動運用と計測
