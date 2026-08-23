"""raw_documents / citations の永続化。source_id + content_hash で既知記事を判定し、
同じ内容を重複して生成・課金しないようにする。
"""

from __future__ import annotations

from uuid import UUID

from src.models.primary_source import Citation, RawDocument
from src.store import supabase_client as sb


async def existing_content_hashes(source_id: str) -> set[str]:
    rows = await sb.select(
        "raw_documents", params={"source_id": f"eq.{source_id}", "select": "content_hash"}
    )
    return {r["content_hash"] for r in rows}


async def save_raw_document(document: RawDocument) -> UUID:
    payload = {
        "id": str(document.id),
        "source_id": document.source_id,
        "fetch_type": document.fetch_type.value,
        "url": document.url,
        "title": document.title,
        "published_at": document.published_at.isoformat() if document.published_at else None,
        "fetched_at": document.fetched_at.isoformat(),
        "content_hash": document.content_hash,
        "raw_text": document.raw_text,
        "page_offsets": [p.model_dump(mode="json") for p in document.page_offsets],
        "license_snapshot": document.license_snapshot.model_dump(mode="json"),
    }
    rows = await sb.insert("raw_documents", payload)
    return UUID(rows[0]["id"])


async def save_citation(citation: Citation) -> UUID:
    payload = citation.model_dump(mode="json")
    rows = await sb.insert("citations", payload)
    return UUID(rows[0]["id"])
