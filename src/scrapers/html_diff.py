"""HTML差分検知。ページ本文を抽出しハッシュ化する。前回ハッシュとの比較（更新有無判定）は
呼び出し側（source_health永続化層）の責務とし、ここでは常に最新状態の RawDocument を返す。
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from src.models.primary_source import LicenseSnapshot, RawDocument
from src.models.source import SourceConfig
from src.scrapers.base import content_hash, fetch_bytes

_NOISE_TAGS = ("script", "style", "nav", "header", "footer")


def _extract_text(html: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else "(no title)"
    body = soup.get_text(separator="\n", strip=True)
    return title, body


async def fetch(client: httpx.AsyncClient, source: SourceConfig) -> list[RawDocument]:
    raw_bytes = await fetch_bytes(client, source)
    title, body = _extract_text(raw_bytes)
    snapshot = LicenseSnapshot(
        license=source.license,
        attribution_required=source.attribution_required,
        redistribution=source.redistribution,
        quote_max_ratio=source.quote_max_ratio,
    )
    document = RawDocument(
        source_id=source.id,
        fetch_type=source.fetch_type,
        url=source.url,
        title=title,
        content_hash=content_hash(body),
        raw_text=body,
        license_snapshot=snapshot,
    )
    return [document]
