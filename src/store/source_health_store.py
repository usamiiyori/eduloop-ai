"""source_health の永続化版。src/scrapers/health.py と同じ判定ロジック（3回連続失敗で通知）を
Supabase上のsource_healthテーブルに対して行う。scrapers.health（インメモリ版）はユニットテスト用
に残し、L1パイプライン（本番実行）はこちらを使う（呼び出し側のインターフェースはほぼ同一）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.metrics import SourceHealth
from src.store import supabase_client as sb

NOTIFY_THRESHOLD = 3


async def get(source_id: str) -> SourceHealth | None:
    rows = await sb.select("source_health", params={"source_id": f"eq.{source_id}"})
    if not rows:
        return None
    return SourceHealth.model_validate(rows[0])


async def record_success(source_id: str) -> SourceHealth:
    payload = {
        "source_id": source_id,
        "last_success_at": datetime.now(UTC).isoformat(),
        "consecutive_failures": 0,
        "last_error": "",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    rows = await sb.insert("source_health", payload, on_conflict="source_id")
    return SourceHealth.model_validate(rows[0])


async def record_failure(source_id: str, error: str) -> SourceHealth:
    current = await get(source_id)
    consecutive = (current.consecutive_failures if current else 0) + 1
    payload = {
        "source_id": source_id,
        "last_failure_at": datetime.now(UTC).isoformat(),
        "consecutive_failures": consecutive,
        "last_error": error,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if current and current.last_success_at:
        payload["last_success_at"] = current.last_success_at.isoformat()
    rows = await sb.insert("source_health", payload, on_conflict="source_id")
    return SourceHealth.model_validate(rows[0])


async def should_notify_owner(source_id: str) -> bool:
    health = await get(source_id)
    return health is not None and health.consecutive_failures >= NOTIFY_THRESHOLD


async def all_health() -> list[SourceHealth]:
    rows = await sb.select("source_health", params={"select": "*"})
    return [SourceHealth.model_validate(r) for r in rows]
