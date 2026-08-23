"""PDF収集。本文抽出とページ番号保持（引用時に「p.12」まで出せるように）を行う。"""

from __future__ import annotations

import io

import httpx
import pdfplumber

from src.models.primary_source import LicenseSnapshot, PageOffset, RawDocument
from src.models.source import SourceConfig
from src.scrapers.base import content_hash, fetch_bytes


async def fetch(client: httpx.AsyncClient, source: SourceConfig) -> list[RawDocument]:
    raw_bytes = await fetch_bytes(client, source)

    text_parts: list[str] = []
    page_offsets: list[PageOffset] = []
    cursor = 0
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            start = cursor
            text_parts.append(page_text)
            cursor += len(page_text) + 1  # +1: ページ区切りの改行分
            page_offsets.append(
                PageOffset(page_number=page_number, char_start=start, char_end=cursor - 1)
            )

    raw_text = "\n".join(text_parts)
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
        title=source.name,
        content_hash=content_hash(raw_text),
        raw_text=raw_text,
        page_offsets=page_offsets,
        license_snapshot=snapshot,
    )
    return [document]
