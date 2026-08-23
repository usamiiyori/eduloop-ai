"""drafts / web_articles / x_thread_posts / youtube_scripts / harness_runs / harness_gate_results
の永続化。L1パイプラインが生成・検証したDraftをSupabaseに書き込む唯一の窓口。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.models.draft import Draft, DraftFormat
from src.models.harness import HarnessRun
from src.store import supabase_client as sb


async def save_draft(draft: Draft) -> UUID:
    payload = {
        "id": str(draft.id),
        "raw_document_ids": [str(i) for i in draft.raw_document_ids],
        "format": draft.format.value,
        "status": draft.status.value,
        "fact": draft.key_points.fact,
        "implication": draft.key_points.implication,
        "discussion": draft.key_points.discussion,
        "citation_ids": [str(i) for i in draft.key_points.citation_ids],
        "score_impact": draft.score_impact,
        "score_timeliness": draft.score_timeliness,
        "score_controversy": draft.score_controversy,
        "retry_count": draft.retry_count,
    }
    rows = await sb.insert("drafts", payload)
    return UUID(rows[0]["id"])


async def save_format_content(format_: DraftFormat, structure_raw: dict[str, Any]) -> None:
    """generator.py の generate_* が返す structure_raw をフォーマット別テーブルへ保存する。"""
    draft_id = str(structure_raw["draft_id"])

    if format_ is DraftFormat.WEB_ARTICLE:
        await sb.insert(
            "web_articles",
            {
                "draft_id": draft_id,
                "title": structure_raw["title"],
                "slug": structure_raw["slug"],
                "body_markdown": structure_raw["body_markdown"],
                "utm_campaign": structure_raw["utm_campaign"],
            },
        )
        return

    if format_ is DraftFormat.X_THREAD:
        posts = [
            {"draft_id": draft_id, "order_index": p["order_index"], "text": p["text"]}
            for p in structure_raw["posts"]
        ]
        await sb.insert("x_thread_posts", posts)
        return

    if format_ is DraftFormat.YOUTUBE_SCRIPT:
        await sb.insert(
            "youtube_scripts",
            {
                "draft_id": draft_id,
                "script_text": structure_raw["script_text"],
                "description_text": structure_raw["description_text"],
            },
        )
        return

    raise ValueError(f"未知のDraftFormatです: {format_!r}")


async def recent_published_web_article_bodies(limit: int = 100) -> list[str]:
    """G5重複判定用。公開済みWeb記事の本文を新しい順に取得する。"""
    draft_rows = await sb.select(
        "drafts",
        params={
            "select": "id",
            "status": "eq.published",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    if not draft_rows:
        return []
    ids = ",".join(r["id"] for r in draft_rows)
    article_rows = await sb.select(
        "web_articles", params={"select": "body_markdown", "draft_id": f"in.({ids})"}
    )
    return [r["body_markdown"] for r in article_rows]


async def update_draft_status(
    draft_id: UUID, status: str, *, retry_count: int | None = None
) -> None:
    values: dict[str, Any] = {"status": status}
    if retry_count is not None:
        values["retry_count"] = retry_count
    await sb.update("drafts", match={"id": str(draft_id)}, values=values)


async def save_harness_runs(runs: list[HarnessRun]) -> None:
    for run in runs:
        rows = await sb.insert(
            "harness_runs", {"draft_id": str(run.draft_id), "attempt": run.attempt}
        )
        harness_run_id = rows[0]["id"]
        gate_rows = [
            {
                "harness_run_id": harness_run_id,
                "gate": result.gate.value,
                "passed": result.passed,
                "reason": result.reason,
            }
            for result in run.results
        ]
        await sb.insert("harness_gate_results", gate_rows)
