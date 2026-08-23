"""publishers層のテスト。外部への実接続は行わずモックする。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.draft import Draft, DraftFormat, DraftStatus, KeyPoints
from src.publishers.note_formatter import format_for_note
from src.publishers.revenue_funnel import append_revenue_funnel
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


class TestEmailNotify:
    async def test_skips_silently_when_not_configured(self) -> None:
        from src.publishers.email_notify import send_email

        with patch("src.publishers.email_notify.get_settings") as mock_settings:
            mock_settings.return_value.smtp_user = ""
            mock_settings.return_value.smtp_app_password = ""
            mock_settings.return_value.notify_to_email = ""
            # 例外を出さず、静かに何もしないことを確認する(他の処理を止めないため)。
            await send_email("件名", "本文")

    async def test_sends_via_smtp_with_app_password(self) -> None:
        from src.publishers.email_notify import send_email

        fake_server = MagicMock()
        fake_smtp_cm = MagicMock()
        fake_smtp_cm.__enter__.return_value = fake_server
        fake_smtp_cm.__exit__.return_value = False

        with (
            patch("src.publishers.email_notify.get_settings") as mock_settings,
            patch("smtplib.SMTP", return_value=fake_smtp_cm) as mock_smtp_class,
        ):
            mock_settings.return_value.smtp_host = "smtp.gmail.com"
            mock_settings.return_value.smtp_port = 587
            mock_settings.return_value.smtp_user = "bot@example.com"
            mock_settings.return_value.smtp_app_password = "app-password"
            mock_settings.return_value.notify_to_email = "owner@example.com"

            await send_email("テスト件名", "テスト本文")

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        fake_server.starttls.assert_called_once()
        fake_server.login.assert_called_once_with("bot@example.com", "app-password")
        fake_server.sendmail.assert_called_once()
        args, _ = fake_server.sendmail.call_args
        assert args[0] == "bot@example.com"
        assert args[1] == ["owner@example.com"]

        from email import message_from_string

        sent_message = message_from_string(args[2])
        assert sent_message["From"] == "bot@example.com"
        assert sent_message["To"] == "owner@example.com"
        assert sent_message.get_payload(decode=True).decode("utf-8") == "テスト本文"


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
