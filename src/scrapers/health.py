"""source_health の記録。Phase 2時点ではインメモリ実装。Supabase接続後は同インターフェースの
永続化実装に差し替える（呼び出し側のコードは変更不要）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.metrics import SourceHealth

NOTIFY_THRESHOLD = 3  # 3回連続失敗でオーナー通知（CLAUDE.md 第3章）

_state: dict[str, SourceHealth] = {}


def record_success(source_id: str) -> SourceHealth:
    health = _state.setdefault(source_id, SourceHealth(source_id=source_id))
    health.last_success_at = datetime.now(UTC)
    health.consecutive_failures = 0
    health.last_error = ""
    return health


def record_failure(source_id: str, error: str) -> SourceHealth:
    health = _state.setdefault(source_id, SourceHealth(source_id=source_id))
    health.last_failure_at = datetime.now(UTC)
    health.consecutive_failures += 1
    health.last_error = error
    return health


def should_notify_owner(source_id: str) -> bool:
    health = _state.get(source_id)
    return health is not None and health.consecutive_failures >= NOTIFY_THRESHOLD


def get(source_id: str) -> SourceHealth | None:
    return _state.get(source_id)


def all_health() -> list[SourceHealth]:
    return list(_state.values())
