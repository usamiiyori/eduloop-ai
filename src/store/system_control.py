"""system_control（キルスイッチ）の読み書き。`make stop` が paused=true にし、
L1/L2/L3の各パイプラインは実行開始時にこれを確認して true なら何もせず終了する。
"""

from __future__ import annotations

from src.store import supabase_client as sb


async def is_paused() -> tuple[bool, str]:
    rows = await sb.select("system_control", params={"select": "paused,paused_reason"})
    if not rows:
        return False, ""
    return bool(rows[0]["paused"]), str(rows[0].get("paused_reason") or "")


async def set_paused(paused: bool, reason: str = "") -> None:
    await sb.update(
        "system_control",
        match={"id": "true"},
        values={"paused": paused, "paused_reason": reason},
    )
