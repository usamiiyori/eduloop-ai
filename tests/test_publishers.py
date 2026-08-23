"""publishers層のテスト。Slack通知は実サイトへ接続せずrespxでモックする。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
import respx

from src.models.draft import Draft, DraftFormat, DraftStatus, KeyPoints
from src.publishers.note_formatter import format_for_note
from src.publishers.revenue_funnel import append_revenue_funnel
from src.publishers.review_request import MissingWebhookError, notify_review_needed
from src.publishers.utm import build_utm_url
from src.publishers.web_publish import NotApprovedError, publish_web_article
from src.publishers.x_publisher import format_thread_for_manual_posting, publish_x_thread


def make_draft(status: DraftStatus = DraftStatus.DRAFT) -> Draft:
    return Draft(
        raw_document_ids=[uuid4()],
        format=DraftFormat.WEB_ARTICLE,
        status=status,
        key_points=KeyPoints(fact="a", implication="b", discussion="c"),
        score_impact=4,
        score_timeliness=5,
        score_controversy=3,
    )


class TestUtm:
    def test_adds_utm_params(self) -> None:
        url = build_utm_url(
            "https://example.com/article", source="x", medium="social", campaign="c1"
        )
        assert "utm_source=x" in url
        assert "utm_medium=social" in url
        assert "utm_campaign=c1" in url

    def test_preserves_existing_query(self) -> None:
        url = build_utm_url(
            "https://example.com/article?ref=abc", source="x", medium="social", campaign="c1"
        )
        assert "ref=abc" in url
        assert "utm_source=x" in url

    def test_content_param_optional(self) -> None:
        url = build_utm_url(
            "https://example.com/", source="x", medium="social", campaign="c1", content="post1"
        )
        assert "utm_content=post1" in url


class TestRevenueFunnel:
    def test_appends_note_and_contact_links(self) -> None:
        result = append_revenue_funnel(
            "本文です",
            slug="test-slug",
            note_url="https://note.com/example",
            contact_url="https://example.com/contact",
        )
        assert "本文です" in result
        assert "note.com" in result
        assert "utm_campaign=test-slug" in result
        assert "ご相談" in result

    def test_omits_note_link_when_not_configured(self) -> None:
        result = append_revenue_funnel(
            "本文です", slug="test-slug", note_url=None, contact_url="https://example.com/contact"
        )
        assert "note" not in result.lower()
        assert "ご相談" in result


class TestNoteFormatter:
    def test_formats_title_and_sections(self) -> None:
        body = "## 事実\nA\n## 含意\nB"
        result = format_for_note("タイトル", body)
        assert result.startswith("# タイトル")
        assert "---" in result
        assert "## 事実" in result


class TestXPublisher:
    def test_format_thread_numbers_posts(self) -> None:
        formatted = format_thread_for_manual_posting(["投稿A", "投稿B"])
        assert "1/2\n投稿A" in formatted
        assert "2/2\n投稿B" in formatted

    async def test_draft_mode_does_not_call_api(self) -> None:
        with patch("src.publishers.x_publisher.get_settings") as mock_settings:
            mock_settings.return_value.x_publish_mode = "draft"
            result = await publish_x_thread(["投稿A"])
        assert result.posted is False
        assert result.mode == "draft"

    async def test_api_mode_raises_clear_not_implemented_error(self) -> None:
        with patch("src.publishers.x_publisher.get_settings") as mock_settings:
            mock_settings.return_value.x_publish_mode = "api"
            with pytest.raises(NotImplementedError, match="従量課金"):
                await publish_x_thread(["投稿A"])


class TestReviewRequest:
    async def test_missing_webhook_raises_japanese_error(self) -> None:
        with patch("src.publishers.review_request.get_settings") as mock_settings:
            mock_settings.return_value.slack_webhook_url = ""
            with pytest.raises(MissingWebhookError, match="SLACK_WEBHOOK_URL"):
                await notify_review_needed(make_draft(), "テスト記事", "https://example.com/r/1")

    async def test_posts_payload_to_webhook(self) -> None:
        async with respx.mock:
            route = respx.post("https://hooks.slack.com/services/test").mock(
                return_value=httpx.Response(200, content=b"ok")
            )
            with patch("src.publishers.review_request.get_settings") as mock_settings:
                mock_settings.return_value.slack_webhook_url = "https://hooks.slack.com/services/test"
                await notify_review_needed(make_draft(), "テスト記事", "https://example.com/r/1")
        assert route.called
        sent_body = route.calls.last.request.content.decode("utf-8")
        assert "テスト記事" in sent_body


class TestWebPublish:
    async def test_rejects_unapproved_draft(self) -> None:
        draft = make_draft(status=DraftStatus.DRAFT)
        store = AsyncMock()
        with pytest.raises(NotApprovedError):
            await publish_web_article(
                draft,
                "本文",
                slug="s",
                note_url=None,
                contact_url="https://example.com/contact",
                store=store,
            )
        store.mark_published.assert_not_called()

    async def test_publishes_approved_draft_with_funnel(self) -> None:
        draft = make_draft(status=DraftStatus.APPROVED)
        store = AsyncMock()
        final_body = await publish_web_article(
            draft,
            "本文",
            slug="s",
            note_url="https://note.com/x",
            contact_url="https://example.com/contact",
            store=store,
        )
        assert "本文" in final_body
        assert "note.com" in final_body
        store.mark_published.assert_awaited_once_with(draft.id, final_body)
