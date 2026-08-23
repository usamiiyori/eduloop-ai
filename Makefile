.PHONY: setup run doctor test cost stop

# 初回セットアップ（venv作成・依存インストール・.env雛形コピー）
setup:
	python -m venv .venv
	. .venv/bin/activate; pip install -e ".[dev]"; playwright install chromium
	@test -f .env || cp .env.example .env
	@echo "セットアップ完了。.env に各キーを設定してください。"

# 収集〜検証〜（承認済みのみ）配信のパイプラインを1回実行
run:
	python -m src.pipeline.l1_collect
	python -m src.pipeline.l2_publish

# APIキー・DB接続・各ソース疎通・直近実行結果を日本語で診断
doctor:
	python -m src.pipeline.doctor

# pytest + ruff + mypy を実行
test:
	pytest
	ruff check .
	mypy src

# 当月のLLM API推定コストを日本語で表示
cost:
	python -m src.pipeline.cost

# キルスイッチ: 全自動処理を即停止
stop:
	python -m src.pipeline.stop
