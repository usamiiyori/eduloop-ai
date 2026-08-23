"""レビュー依頼の日次まとめメール。L1は記事ごとに即時通知せず、この処理が1日1回
（GitHub Actions cronで夕方JST想定）、その時点でレビュー待ち(draft/needs_human)の
記事を一覧化してメールで届ける（2026-08-23、オーナーの希望により逐次Slack通知から変更）。

レビュー待ちが0件でも「異常なく稼働している」ことが分かるよう、その旨を1通送る
（何日も届かない状態こそが「パイプラインが止まっている」サインになるため）。
"""

from __future__ import annotations

import asyncio

import structlog

from src.config import get_settings
from src.publishers import email_notify
from src.store import supabase_client as sb
from src.store import system_control

logger = structlog.get_logger(__name__)


async def _title_for(draft_id: str, format_: str) -> str:
    if format_ == "web_article":
        rows = await sb.select(
            "web_articles", params={"select": "title", "draft_id": f"eq.{draft_id}"}
        )
        if rows:
            title: str = rows[0]["title"]
            return title
    return f"{format_} ({draft_id[:8]})"


async def _pending_summaries() -> list[dict[str, object]]:
    rows = await sb.select(
        "drafts",
        params={
            "select": "id,format,status,score_impact,score_timeliness,score_controversy,created_at",
            "status": "in.(draft,needs_human)",
            "order": "created_at.asc",
        },
    )
    summaries: list[dict[str, object]] = []
    for row in rows:
        title = await _title_for(row["id"], row["format"])
        score_total = row["score_impact"] * row["score_timeliness"] * row["score_controversy"]
        summaries.append({**row, "title": title, "score_total": score_total})
    return summaries


def _format_digest(summaries: list[dict[str, object]], review_url: str) -> str:
    if not summaries:
        return (
            "本日時点でレビュー待ちの記事はありません。パイプラインは正常に稼働しています。\n\n"
            f"承認画面: {review_url}"
        )

    lines = [f"レビュー待ちの記事が{len(summaries)}件あります。\n"]
    for s in summaries:
        badge = "【要人間レビュー】" if s["status"] == "needs_human" else ""
        lines.append(f"{badge}{s['title']}（スコア{s['score_total']}）")
    lines.append(f"\n承認画面はこちら: {review_url}")
    return "\n".join(lines)


async def run() -> None:
    paused, reason = await system_control.is_paused()
    if paused:
        logger.warning("review_digest_skipped_paused", reason=reason)
        return

    summaries = await _pending_summaries()
    review_url = get_settings().review_app_url
    body = _format_digest(summaries, review_url)
    logger.info("review_digest_sent", pending_count=len(summaries))
    await email_notify.send_email(
        f"[EduLoop AI] 本日のレビュー依頼まとめ（{len(summaries)}件）", body
    )


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
