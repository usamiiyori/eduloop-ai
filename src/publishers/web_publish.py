"""L2承認後のWeb記事公開ロジック。承認フラグ未確認での実行を禁止する（CLAUDE.md 第2章）。

Phase5時点ではSupabaseプロジェクトが未接続のため、実際の永続化は PublishStore
プロトコル経由の依存性注入とする。Supabase接続後（Phase6）、supabase-pyクライアントを
使った具象実装に差し替える（呼び出し側のコードは変更不要）。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.models.draft import Draft, DraftStatus
from src.publishers.revenue_funnel import append_revenue_funnel


class NotApprovedError(RuntimeError):
    def __init__(self, draft_id: UUID) -> None:
        super().__init__(
            f"draft {draft_id} はまだ承認(approved)されていません。"
            "L2承認前のコンテンツは配信できません（CLAUDE.md 第2章・第11章の禁止事項）。"
        )


class PublishStore(Protocol):
    async def mark_published(self, draft_id: UUID, final_body_markdown: str) -> None: ...


async def publish_web_article(
    draft: Draft,
    body_markdown: str,
    *,
    slug: str,
    note_url: str | None,
    contact_url: str,
    store: PublishStore,
) -> str:
    """承認済み(approved)のdraftのみ受け付け、収益導線を追記した最終本文を永続化する。"""
    if draft.status != DraftStatus.APPROVED:
        raise NotApprovedError(draft.id)

    final_body = append_revenue_funnel(
        body_markdown, slug=slug, note_url=note_url, contact_url=contact_url
    )
    await store.mark_published(draft.id, final_body)
    return final_body
