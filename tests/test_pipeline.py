"""Phase6: パイプライン層・コスト見積り・自己修復プロンプト注入のテスト。"""

from __future__ import annotations

from src.models.primary_source import LicenseSnapshot, RawDocument
from src.models.source import FetchType, LicenseType, RedistributionMode
from src.pipeline.l1_collect import _dedup_new_documents
from src.processors.context import build_default_context
from src.processors.pricing import estimate_cost_usd
from src.processors.prompt_builder import build_extraction_prompt


def _doc(source_id: str, content_hash: str) -> RawDocument:
    return RawDocument(
        source_id=source_id,
        fetch_type=FetchType.RSS,
        url="https://example.com/a",
        title="t",
        content_hash=content_hash,
        raw_text="text",
        license_snapshot=LicenseSnapshot(
            license=LicenseType.GOV_STANDARD_TERMS_2_0,
            attribution_required=True,
            redistribution=RedistributionMode.FULL_ALLOWED,
            quote_max_ratio=None,
        ),
    )


class TestPricing:
    def test_confirmed_model_computes_cost(self) -> None:
        estimate = estimate_cost_usd(
            "gemini-2.5-flash", input_tokens=1_000_000, output_tokens=1_000_000
        )
        assert estimate.confirmed is True
        assert round(estimate.usd, 2) == 2.80  # 0.30 + 2.50

    def test_unconfirmed_model_returns_zero_and_flags_unconfirmed(self) -> None:
        estimate = estimate_cost_usd("gemini-embedding-001", input_tokens=1000, output_tokens=1000)
        assert estimate.confirmed is False
        assert estimate.usd == 0.0


class TestSelfRepairPromptInjection:
    def test_prior_failures_are_injected(self) -> None:
        raw_document = _doc("s1", "h1")
        context = build_default_context()
        prompt = build_extraction_prompt(
            raw_document, context, prior_failures=["G4: 断定表現を検出"]
        )
        assert "前回の生成で指摘された問題点" in prompt
        assert "G4: 断定表現を検出" in prompt

    def test_no_prior_failures_omits_section(self) -> None:
        raw_document = _doc("s1", "h1")
        context = build_default_context()
        prompt = build_extraction_prompt(raw_document, context)
        assert "前回の生成で指摘された問題点" not in prompt


class TestDedupNewDocuments:
    def test_skips_known_content_hash(self) -> None:
        docs = [_doc("s1", "known"), _doc("s1", "new")]
        result = _dedup_new_documents(docs, known_hashes={"s1": {"known"}})
        assert [d.content_hash for d in result] == ["new"]

    def test_caps_new_docs_per_source(self) -> None:
        docs = [_doc("s1", f"h{i}") for i in range(10)]
        result = _dedup_new_documents(docs, known_hashes={})
        assert len(result) == 5  # MAX_NEW_DOCS_PER_SOURCE

    def test_different_sources_have_independent_caps(self) -> None:
        docs = [_doc("s1", f"a{i}") for i in range(5)] + [_doc("s2", f"b{i}") for i in range(5)]
        result = _dedup_new_documents(docs, known_hashes={})
        assert len(result) == 10
