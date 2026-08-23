"""llm_cost_log の記録・集計。日次コスト上限判定（自動停止）と
`make cost` / `make doctor` が使う。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.processors.pricing import estimate_cost_usd
from src.store import supabase_client as sb


async def record_usage(
    *, model: str, purpose: str, input_tokens: int, output_tokens: int, draft_id: UUID | None = None
) -> None:
    estimate = estimate_cost_usd(model, input_tokens, output_tokens)
    await sb.insert(
        "llm_cost_log",
        {
            "draft_id": str(draft_id) if draft_id else None,
            "purpose": purpose,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": round(estimate.usd, 6),
        },
    )


async def total_cost_usd_since(since: datetime) -> float:
    rows = await sb.select(
        "llm_cost_log",
        params={
            "select": "estimated_cost_usd",
            "created_at": f"gte.{since.astimezone(UTC).isoformat()}",
        },
    )
    return sum(float(r["estimated_cost_usd"]) for r in rows)


async def today_total_usd() -> float:
    start_of_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return await total_cost_usd_since(start_of_today)


async def month_total_usd() -> float:
    start_of_month = datetime.now(UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return await total_cost_usd_since(start_of_month)
