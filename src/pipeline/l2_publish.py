"""L2: Web承認画面で承認(approved)された記事をSupabaseから検知し、配信物を仕上げてSlackで
オーナーに届ける。GitHub Actions cron(日次)から実行する。

「配信」の意味はフォーマットによって異なる（docs/ARCHITECTURE.md 8章）:
  - Web記事: 収益導線を追記して web_articles に反映し、公開(published)とする
    （唯一の完全自動チャネル）。
  - Xスレッド/YouTube台本: コピペ用の下書きテキストをSlackに届けて公開(published)とする。
    実際の投稿・録画はオーナーの手作業（X APIが有料化されているため、ARCHITECTURE.md 8章の方針
    通りdraftモードのみ提供する）。
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog

from src.config import get_settings
from src.models.draft import Draft, DraftFormat, KeyPoints
from src.publishers import note_formatter, slack_notify, x_publisher
from src.publishers.web_publish import publish_web_article
from src.store import supabase_client as sb
from src.store import system_control

logger = structlog.get_logger(__name__)

_SLACK_BODY_PREVIEW_LIMIT = 3000


def _draft_from_row(row: dict[str, Any]) -> Draft:
    return Draft(
        id=UUID(row["id"]),
        raw_document_ids=[UUID(i) for i in row["raw_document_ids"]],
        format=DraftFormat(row["format"]),
        status=row["status"],
        key_points=KeyPoints(
            fact=row["fact"],
            implication=row["implication"],
            discussion=row["discussion"],
            citation_ids=[UUID(i) for i in row["citation_ids"]],
        ),
        score_impact=row["score_impact"],
        score_timeliness=row["score_timeliness"],
        score_controversy=row["score_controversy"],
        retry_count=row["retry_count"],
    )


class SupabasePublishStore:
    async def mark_published(self, draft_id: UUID, final_body_markdown: str) -> None:
        await sb.update("drafts", match={"id": str(draft_id)}, values={"status": "published"})
        await sb.update(
            "web_articles",
            match={"draft_id": str(draft_id)},
            values={"body_markdown": final_body_markdown},
        )


def _truncate(text: str) -> str:
    if len(text) <= _SLACK_BODY_PREVIEW_LIMIT:
        return text
    return text[:_SLACK_BODY_PREVIEW_LIMIT] + "\n…（以下省略。全文はSupabaseを参照）"


async def _publish_web_article(draft: Draft) -> None:
    rows = await sb.select("web_articles", params={"draft_id": f"eq.{draft.id}"})
    article = rows[0]
    settings = get_settings()

    if settings.contact_url:
        # publish_web_article (src/publishers/web_publish.py) がapproved確認+収益導線追記+
        # 永続化までを担う（CONTACT_URL未設定時に壊れたリンクを付けないよう、ここでは
        # contact_urlが設定済みの場合のみこの経路を使う）。
        final_body = await publish_web_article(
            draft,
            article["body_markdown"],
            slug=article["slug"],
            note_url=settings.note_url or None,
            contact_url=settings.contact_url,
            store=SupabasePublishStore(),
        )
    else:
        final_body = article["body_markdown"]
        await SupabasePublishStore().mark_published(draft.id, final_body)

    note_draft = note_formatter.format_for_note(article["title"], final_body)
    await slack_notify.send_text(
        f":tada: Web記事を公開しました: {article['title']}\n\n"
        f"--- note下書き（コピペ用） ---\n{_truncate(note_draft)}"
    )


async def _publish_x_thread(draft: Draft) -> None:
    rows = await sb.select(
        "x_thread_posts", params={"draft_id": f"eq.{draft.id}", "order": "order_index.asc"}
    )
    posts = [r["text"] for r in rows]
    result = await x_publisher.publish_x_thread(posts)
    await sb.update("drafts", match={"id": str(draft.id)}, values={"status": "published"})
    await slack_notify.send_text(
        ":tada: Xスレッドの下書きができました（手動投稿してください）\n\n"
        f"{_truncate(result.formatted_text)}"
    )


async def _publish_youtube_script(draft: Draft) -> None:
    rows = await sb.select("youtube_scripts", params={"draft_id": f"eq.{draft.id}"})
    script = rows[0]
    await sb.update("drafts", match={"id": str(draft.id)}, values={"status": "published"})
    await slack_notify.send_text(
        ":tada: YouTube台本ができました\n\n"
        f"--- 台本 ---\n{_truncate(script['script_text'])}\n\n"
        f"--- 概要欄 ---\n{_truncate(script['description_text'])}"
    )


async def run() -> None:
    paused, reason = await system_control.is_paused()
    if paused:
        logger.warning("l2_skipped_paused", reason=reason)
        return

    rows = await sb.select("drafts", params={"status": "eq.approved"})
    if not rows:
        logger.info("l2_no_approved_drafts")
        return

    for row in rows:
        draft = _draft_from_row(row)
        try:
            if draft.format is DraftFormat.WEB_ARTICLE:
                await _publish_web_article(draft)
            elif draft.format is DraftFormat.X_THREAD:
                await _publish_x_thread(draft)
            elif draft.format is DraftFormat.YOUTUBE_SCRIPT:
                await _publish_youtube_script(draft)
        except Exception:  # noqa: BLE001 — 1件の失敗が他の記事の配信を止めないようにする
            logger.exception("l2_publish_failed", draft_id=str(draft.id))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
