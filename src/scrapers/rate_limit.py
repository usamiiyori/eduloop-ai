"""ソース単位のレート制限。source.crawl_interval_seconds（最低3秒）を尊重する。"""

from __future__ import annotations

import asyncio
import time

_last_request_at: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


async def wait_for_turn(source_id: str, interval_seconds: int) -> None:
    """同一ソースへの前回リクエストから interval_seconds 経過するまで待機する。"""
    lock = _locks.setdefault(source_id, asyncio.Lock())
    async with lock:
        last = _last_request_at.get(source_id)
        if last is not None:
            elapsed = time.monotonic() - last
            remaining = interval_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        _last_request_at[source_id] = time.monotonic()
