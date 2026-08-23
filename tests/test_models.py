"""Pydantic v2 モデルのバリデーション検証。特に「壊れた」入力を弾けることを確認する。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.draft import WebArticle, XPost, XThread
from src.models.source import RedistributionMode, SourceConfig, load_sources


class TestSourceConfig:
    def _base(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "id": "test_source",
            "name": "テストソース",
            "axis": "a_policy_jp",
            "fetch_type": "html_diff",
            "url": "https://example.go.jp/",
            "license": "gov_standard_terms_2_0",
            "attribution_required": True,
            "redistribution": "full_allowed",
        }
        base.update(overrides)
        return base

    def test_full_allowed_without_quote_ratio_is_valid(self) -> None:
        SourceConfig.model_validate(self._base())

    def test_quote_only_requires_quote_max_ratio(self) -> None:
        with pytest.raises(ValidationError, match="quote_max_ratio が必須"):
            SourceConfig.model_validate(
                self._base(redistribution=RedistributionMode.QUOTE_ONLY, license="unconfirmed")
            )

    def test_quote_max_ratio_forbidden_outside_quote_only(self) -> None:
        with pytest.raises(ValidationError, match="quote_only の時のみ"):
            SourceConfig.model_validate(self._base(quote_max_ratio=0.1))

    def test_quote_max_ratio_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="0〜1 の範囲"):
            SourceConfig.model_validate(
                self._base(
                    redistribution=RedistributionMode.QUOTE_ONLY,
                    license="unconfirmed",
                    quote_max_ratio=1.5,
                )
            )

    def test_load_real_sources_yaml(self) -> None:
        sources = load_sources("config/sources.yaml")
        assert len(sources) > 0
        for source in sources:
            if source.redistribution == RedistributionMode.QUOTE_ONLY:
                assert source.quote_max_ratio is not None


class TestWebArticle:
    def test_missing_required_section_rejected(self) -> None:
        with pytest.raises(ValidationError, match="4部構成"):
            WebArticle.model_validate(
                {
                    "draft_id": uuid4(),
                    "title": "テスト記事",
                    "slug": "test",
                    "body_markdown": "事実だけ書いてある本文",
                    "citation_ids": [uuid4()],
                    "utm_campaign": "test_campaign",
                }
            )

    def test_all_four_sections_present_is_valid(self) -> None:
        body = "## 事実\nA\n## 含意\nB\n## 論点\nC\n## 出典\nD"
        WebArticle.model_validate(
            {
                "draft_id": uuid4(),
                "title": "テスト記事",
                "slug": "test",
                "body_markdown": body,
                "citation_ids": [uuid4()],
                "utm_campaign": "test_campaign",
            }
        )


class TestXThread:
    def test_order_index_must_be_contiguous_from_zero(self) -> None:
        with pytest.raises(ValidationError, match="0 から連番"):
            XThread.model_validate(
                {
                    "draft_id": uuid4(),
                    "posts": [
                        {"order_index": 0, "text": "1"},
                        {"order_index": 2, "text": "2"},
                        {"order_index": 3, "text": "3"},
                    ],
                }
            )

    def test_valid_thread(self) -> None:
        XThread.model_validate(
            {
                "draft_id": uuid4(),
                "posts": [XPost(order_index=i, text=f"投稿{i}") for i in range(3)],
            }
        )

    def test_post_over_140_chars_rejected(self) -> None:
        with pytest.raises(ValidationError):
            XPost.model_validate({"order_index": 0, "text": "あ" * 141})
