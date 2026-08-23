"""RSS/Atom収集。feedparserでパースし、フィード内の各エントリを RawDocument に変換する。"""

from __future__ import annotations

from datetime import datetime
from time import mktime

import feedparser
import httpx
import structlog

from src.models.primary_source import LicenseSnapshot, RawDocument
from src.models.source import SourceConfig
from src.scrapers.base import content_hash, fetch_bytes

logger = structlog.get_logger(__name__)


def _license_snapshot(source: SourceConfig) -> LicenseSnapshot:
    return LicenseSnapshot(
        license=source.license,
        attribution_required=source.attribution_required,
        redistribution=source.redistribution,
        quote_max_ratio=source.quote_max_ratio,
    )


async def fetch(client: httpx.AsyncClient, source: SourceConfig) -> list[RawDocument]:
    raw_bytes = await fetch_bytes(client, source)
    feed = feedparser.parse(raw_bytes)
    if feed.bozo:
        logger.warning("rss_parse_warning", source_id=source.id, error=str(feed.bozo_exception))

    snapshot = _license_snapshot(source)
    documents: list[RawDocument] = []
    for entry in feed.entries:
        body = entry.get("summary", "") or entry.get("title", "")
        published_at: datetime | None = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
        documents.append(
            RawDocument(
                source_id=source.id,
                fetch_type=source.fetch_type,
                url=entry.get("link", source.url),
                title=entry.get("title", "(no title)"),
                published_at=published_at,
                content_hash=content_hash(body),
                raw_text=body,
                license_snapshot=snapshot,
            )
        )
    return documents
