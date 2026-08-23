"""L3: 月次の知見還元。収益KPI(docs/ARCHITECTURE.md 4章)を集計してSlackへ月次レポートとして
届ける。GitHub Actions cron(月次)から実行する。

Phase6スコープの意図的な簡略化: ソース優先度の自動調整・コンテキスト層への教員フィードバック
反映といった「学習」的な機能は、十分なデータ（教員コメント・実践報告の蓄積）が貯まってから
設計すべきであり、現時点でデータなしに作ると当てずっぽうのロジックになる
（CLAUDE.md第0章ルール5「推測でコードを書かない」）。そのためPhase6のL3は集計・可視化に留め、
自動調整は将来のPhaseで改めて設計する。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from src.publishers import slack_notify
from src.store import supabase_client as sb
from src.store import system_control

logger = structlog.get_logger(__name__)


def _start_of_month() -> datetime:
    return datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _sum_metrics(since: datetime) -> dict[str, float]:
    since_iso = since.isoformat()

    post_metrics = await sb.select(
        "post_metrics",
        params={"select": "impressions,profile_clicks", "recorded_at": f"gte.{since_iso}"},
    )
    link_clicks = await sb.select(
        "link_clicks", params={"select": "id", "clicked_at": f"gte.{since_iso}"}
    )
    conversions = await sb.select(
        "conversions", params={"select": "amount_jpy", "recorded_at": f"gte.{since_iso}"}
    )
    inbound_leads = await sb.select(
        "inbound_leads", params={"select": "id", "created_at": f"gte.{since_iso}"}
    )
    published_drafts = await sb.select(
        "drafts",
        params={"select": "id", "status": "eq.published", "updated_at": f"gte.{since_iso}"},
    )

    return {
        "published_count": len(published_drafts),
        "impressions": sum(r["impressions"] for r in post_metrics),
        "profile_clicks": sum(r["profile_clicks"] for r in post_metrics),
        "link_clicks": len(link_clicks),
        "revenue_jpy": sum(r["amount_jpy"] for r in conversions),
        "inbound_leads": len(inbound_leads),
    }


def _format_report(since: datetime, totals: dict[str, float]) -> str:
    month_label = since.strftime("%Y年%m月")
    return (
        f":bar_chart: {month_label} EduLoop AI 月次レポート\n"
        f"公開記事数: {int(totals['published_count'])}件\n"
        f"インプレッション合計: {int(totals['impressions'])}\n"
        f"プロフィールクリック合計: {int(totals['profile_clicks'])}\n"
        f"Web記事へのリンククリック: {int(totals['link_clicks'])}\n"
        f"収益(note等): {int(totals['revenue_jpy'])}円\n"
        f"問い合わせ・登壇依頼: {int(totals['inbound_leads'])}件\n\n"
        "※インプレッション・クリック・収益はほとんどが手動入力です。"
        "実績が反映されていない場合はSupabaseへの入力をお願いします。"
    )


async def run() -> None:
    paused, reason = await system_control.is_paused()
    if paused:
        logger.warning("l3_skipped_paused", reason=reason)
        return

    since = _start_of_month()
    totals = await _sum_metrics(since)
    report = _format_report(since, totals)
    logger.info("l3_monthly_report", **totals)
    await slack_notify.send_text(report)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
