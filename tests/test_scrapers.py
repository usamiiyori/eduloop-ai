"""スクレイパー層のテスト。CLAUDE.md方針どおり実サイトへの実リクエストは一切行わず、
tests/fixtures/ の固定データと respx によるHTTPモックのみを用いてパースロジックを検証する。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from src.models.source import FetchType, SourceConfig
from src.scrapers import html_diff, pdf, rss, runner
from src.scrapers.base import RobotsDisallowedError, content_hash, fetch_bytes
from src.scrapers.robots import is_allowed

FIXTURES = Path(__file__).parent / "fixtures"


def make_source(**overrides: object) -> SourceConfig:
    base: dict[str, object] = {
        "id": "test_source",
        "name": "テストソース",
        "axis": "a_policy_jp",
        "fetch_type": "rss",
        "url": "https://example.test/feed",
        "license": "unconfirmed",
        "attribution_required": True,
        "redistribution": "quote_only",
        "quote_max_ratio": 0.1,
        "crawl_interval_seconds": 3,
    }
    base.update(overrides)
    return SourceConfig.model_validate(base)


class TestContentHash:
    def test_same_text_same_hash(self) -> None:
        assert content_hash("同じテキスト") == content_hash("同じテキスト")

    def test_different_text_different_hash(self) -> None:
        assert content_hash("テキストA") != content_hash("テキストB")


class TestRssScraper:
    async def test_parses_fixture_entries(self) -> None:
        feed_bytes = (FIXTURES / "sample_feed.xml").read_bytes()
        source = make_source(fetch_type="rss", url="https://example.test/feed")

        async with respx.mock:
            respx.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
            respx.get("https://example.test/feed").mock(
                return_value=httpx.Response(200, content=feed_bytes)
            )
            async with httpx.AsyncClient() as client:
                docs = await rss.fetch(client, source)

        assert len(docs) == 2
        assert docs[0].title == "テスト記事1"
        assert "テスト記事1の本文" in docs[0].raw_text
        assert docs[0].source_id == "test_source"
        assert docs[0].published_at is not None
        assert docs[0].license_snapshot.license.value == "unconfirmed"


class TestHtmlDiffScraper:
    async def test_strips_noise_tags(self) -> None:
        html_bytes = (FIXTURES / "sample_page.html").read_bytes()
        source = make_source(fetch_type="html_diff", url="https://example.test/page")

        async with respx.mock:
            respx.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
            respx.get("https://example.test/page").mock(
                return_value=httpx.Response(200, content=html_bytes)
            )
            async with httpx.AsyncClient() as client:
                docs = await html_diff.fetch(client, source)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.title == "テストページ"
        assert "本文の段落です" in doc.raw_text
        assert "ナビゲーション" not in doc.raw_text
        assert "ヘッダー" not in doc.raw_text
        assert "フッター" not in doc.raw_text
        assert "shouldBeExcluded" not in doc.raw_text


class TestPdfScraper:
    async def test_preserves_page_offsets(self) -> None:
        source = make_source(fetch_type="pdf", url="https://example.test/doc.pdf")

        page1 = MagicMock()
        page1.extract_text.return_value = "1ページ目の本文"
        page2 = MagicMock()
        page2.extract_text.return_value = "2ページ目の本文"
        fake_pdf = MagicMock()
        fake_pdf.pages = [page1, page2]
        fake_pdf.__enter__.return_value = fake_pdf
        fake_pdf.__exit__.return_value = False

        async with respx.mock:
            respx.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
            respx.get("https://example.test/doc.pdf").mock(
                return_value=httpx.Response(200, content=b"%PDF-1.4 fake bytes")
            )
            with patch("src.scrapers.pdf.pdfplumber.open", return_value=fake_pdf):
                async with httpx.AsyncClient() as client:
                    docs = await pdf.fetch(client, source)

        assert len(docs) == 1
        doc = docs[0]
        assert "1ページ目の本文" in doc.raw_text
        assert "2ページ目の本文" in doc.raw_text
        assert len(doc.page_offsets) == 2
        assert doc.page_offsets[0].page_number == 1
        assert doc.page_offsets[1].page_number == 2
        # p.12まで出せるよう、オフセットが実際のテキスト位置と一致していること
        p1 = doc.page_offsets[0]
        assert doc.raw_text[p1.char_start : p1.char_end] == "1ページ目の本文"


class TestRobots:
    async def test_disallowed_blocks_fetch(self) -> None:
        source = make_source(url="https://blocked.test/feed")

        async with respx.mock:
            respx.get("https://blocked.test/robots.txt").mock(
                return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
            )
            async with httpx.AsyncClient() as client:
                with pytest.raises(RobotsDisallowedError):
                    await fetch_bytes(client, source)

    async def test_override_bypasses_robots_check(self) -> None:
        source = make_source(
            url="https://blocked.test/feed",
            robots_txt_override=True,
            override_justification="テスト用の根拠",
        )

        async with respx.mock:
            # robots.txt へのリクエスト自体が発生しないことを route未登録のまま確認する。
            respx.get("https://blocked.test/feed").mock(
                return_value=httpx.Response(200, content=b"ok")
            )
            async with httpx.AsyncClient() as client:
                allowed = await is_allowed(client, source, "TestAgent")

        assert allowed is True


class TestRunner:
    """1ソースが長時間ブロックしても他ソースの収集を止めない（2026-08-23のL1初回実行で
    DNS異常のあるソースが全体を11分以上停止させた実障害の再発防止）。"""

    async def test_slow_source_times_out_without_blocking_others(self) -> None:
        slow_source = make_source(id="slow", url="https://slow.test/feed", fetch_type="rss")
        fast_source = make_source(
            id="fast", url="https://fast.test/", fetch_type="html_diff"
        )

        async def slow_fetch(client: httpx.AsyncClient, source: SourceConfig) -> list[object]:
            await asyncio.sleep(10)
            return []

        async def fast_fetch(client: httpx.AsyncClient, source: SourceConfig) -> list[object]:
            return []

        with (
            patch.dict(
                runner._DISPATCH,
                {FetchType.RSS: slow_fetch, FetchType.HTML_DIFF: fast_fetch},
            ),
            patch("src.scrapers.runner._SOURCE_TIMEOUT_SECONDS", 0.05),
        ):
            result = await runner.run_sources([slow_source, fast_source])

        assert "slow" in result.errors
        assert "fast" not in result.errors
