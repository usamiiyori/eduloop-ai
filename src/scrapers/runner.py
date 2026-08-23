"""sources.yaml から動的にソースを読み込み、fetch_typeに応じたスクレイパーへ振り分けて実行する。

1ソースの失敗が他ソースの収集を止めないよう、例外はここで捕捉して source_health に記録する
（CLAUDE.md 第3章: 取得失敗は握りつぶさず記録、3回連続失敗でオーナー通知）。

各ソースの取得には _SOURCE_TIMEOUT_SECONDS のウォッチドッグを設ける。fetch_bytes自体は
timeout=30とtenacityの再試行で個々のHTTP呼び出しを制限しているが、DNS解決の異常など
稀にhttpxのtimeout指定をすり抜けて長時間ブロックするケースが実運用で確認されたため
（2026-08-23、L1初回実行でDNS異常のあるソースが11分以上ブロックし全体が止まった）、
二重の安全策として外側からも上限を設ける。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx
import structlog

from src.models.primary_source import RawDocument
from src.models.source import FetchType, SourceConfig, load_sources
from src.scrapers import health, html_diff, pdf, rss
from src.scrapers.base import build_user_agent

logger = structlog.get_logger(__name__)

_DISPATCH = {
    FetchType.RSS: rss.fetch,
    FetchType.HTML_DIFF: html_diff.fetch,
    FetchType.PDF: pdf.fetch,
}

# fetch_bytesの内部リトライ(timeout30s×3回+バックオフ)より十分大きく取る
_SOURCE_TIMEOUT_SECONDS = 120


@dataclass
class RunResult:
    documents: list[RawDocument] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


async def run_sources(sources: list[SourceConfig]) -> RunResult:
    result = RunResult()
    headers = {"User-Agent": build_user_agent()}
    async with httpx.AsyncClient(headers=headers) as client:
        for source in sources:
            handler = _DISPATCH[source.fetch_type]
            try:
                docs = await asyncio.wait_for(
                    handler(client, source), timeout=_SOURCE_TIMEOUT_SECONDS
                )
                result.documents.extend(docs)
                health.record_success(source.id)
                logger.info("scrape_succeeded", source_id=source.id, doc_count=len(docs))
            except TimeoutError:
                message = f"{_SOURCE_TIMEOUT_SECONDS}秒以内に取得が完了しませんでした"
                result.errors[source.id] = message
                health.record_failure(source.id, message)
                logger.error("scrape_timed_out", source_id=source.id)
                if health.should_notify_owner(source.id):
                    logger.error("scrape_needs_owner_notification", source_id=source.id)
            except Exception as exc:  # noqa: BLE001 — 1ソースの失敗は握りつぶさず記録して続行する
                result.errors[source.id] = f"{type(exc).__name__}: {exc}"
                health.record_failure(source.id, str(exc))
                logger.error("scrape_failed", source_id=source.id, error=str(exc))
                if health.should_notify_owner(source.id):
                    logger.error("scrape_needs_owner_notification", source_id=source.id)
    return result


async def run_all(sources_path: str = "config/sources.yaml") -> RunResult:
    sources = load_sources(sources_path)
    return await run_sources(sources)
