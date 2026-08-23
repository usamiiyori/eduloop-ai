"""生成層(processors)のテスト。LLM呼び出し(generate_structured)はモックし、実際のGemini APIには
接続しない。プロンプト構築・禁止語チェック・スコアリング・そして「生成物がharnessのG6構造ゲートを
実際に通過するか」という統合確認までを行う。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.harness.context import HarnessContext, SourceExcerpt
from src.harness.orchestrator import run_gates
from src.models.draft import DraftFormat
from src.models.editorial import EditorialVoiceConfig
from src.models.primary_source import Citation, LicenseSnapshot, RawDocument
from src.models.source import LicenseType, RedistributionMode
from src.processors import generator, prompt_builder
from src.processors.banned_phrases import find_banned_phrases
from src.processors.context import ContextBundle, build_default_context
from src.processors.schemas import ExtractionOutput, XThreadOutput, YouTubeScriptOutput
from src.processors.scoring import passes_threshold

SOURCE_TEXT = (
    "文部科学省は令和8年3月に生成AIパイロット校の公募を開始する検討会議の資料を公表した。"
    "対象校は全国で20校程度を想定しており、詳細は今後の審議会で議論される予定である。"
)


def make_raw_document() -> RawDocument:
    return RawDocument(
        source_id="mext_chuokyoshin",
        fetch_type="html_diff",
        url="https://www.mext.go.jp/example.htm",
        title="生成AIパイロット校の公募について",
        content_hash="abc123def456",
        raw_text=SOURCE_TEXT,
        license_snapshot=LicenseSnapshot(
            license=LicenseType.GOV_STANDARD_TERMS_2_0,
            attribution_required=True,
            redistribution=RedistributionMode.FULL_ALLOWED,
            quote_max_ratio=None,
        ),
    )


def make_citation(raw_document: RawDocument) -> Citation:
    return Citation(
        raw_document_id=raw_document.id,
        author_or_organization="文部科学省",
        title=raw_document.title,
        url=raw_document.url,
    )


class TestPromptBuilder:
    def test_extraction_prompt_embeds_editorial_voice_and_source(self) -> None:
        context = build_default_context()
        raw_document = make_raw_document()
        prompt = prompt_builder.build_extraction_prompt(raw_document, context)

        assert context.editorial_voice.persona in prompt
        for phrase in context.editorial_voice.banned_phrases:
            assert phrase in prompt
        assert raw_document.title in prompt
        assert raw_document.raw_text in prompt

    def test_context_injection_shows_placeholder_when_empty(self) -> None:
        context = build_default_context()
        raw_document = make_raw_document()
        prompt = prompt_builder.build_extraction_prompt(raw_document, context)
        assert "現時点では参照データなし" in prompt


class TestBannedPhrases:
    def test_detects_banned_phrase(self) -> None:
        voice = EditorialVoiceConfig(
            persona="p",
            banned_phrases=["いかがでしたか"],
            required_sections=["事実", "含意", "論点", "出典"],
            number_rule="r",
            stance_rule="s",
        )
        found = find_banned_phrases("この記事はいかがでしたか？ぜひご意見を。", voice)
        assert found == ["いかがでしたか"]

    def test_clean_text_has_no_hits(self) -> None:
        voice = EditorialVoiceConfig(
            persona="p",
            banned_phrases=["いかがでしたか"],
            required_sections=["事実", "含意", "論点", "出典"],
            number_rule="r",
            stance_rule="s",
        )
        assert find_banned_phrases("これは通常の文章です。", voice) == []


class TestScoring:
    def test_passes_threshold(self) -> None:
        raw_document = make_raw_document()
        extraction = ExtractionOutput(
            fact="a", implication="b", discussion="c",
            score_impact=5, score_timeliness=5, score_controversy=5,
        )
        draft = generator._build_draft(
            raw_document, extraction, DraftFormat.WEB_ARTICLE, uuid4()
        )
        assert draft.score_total == 125
        assert passes_threshold(draft, threshold=27) is True

    def test_below_threshold_is_filtered(self) -> None:
        raw_document = make_raw_document()
        extraction = ExtractionOutput(
            fact="a", implication="b", discussion="c",
            score_impact=1, score_timeliness=1, score_controversy=1,
        )
        draft = generator._build_draft(
            raw_document, extraction, DraftFormat.WEB_ARTICLE, uuid4()
        )
        assert draft.score_total == 1
        assert passes_threshold(draft, threshold=27) is False


class TestWebArticleAssembly:
    def test_assembled_markdown_has_four_sections(self) -> None:
        context = build_default_context()
        extraction = ExtractionOutput(
            fact="事実の内容", implication="含意の内容", discussion="論点の内容",
            score_impact=3, score_timeliness=3, score_controversy=3,
        )
        markdown = generator.assemble_web_article_markdown(extraction, context, "出典: 文科省")
        for section in context.editorial_voice.required_sections:
            assert f"## {section}" in markdown


class TestGenerateWebArticleIntegration:
    """生成層の出力が実際にharness層(Phase3)のG6構造ゲートを通過するかを確認する統合テスト。"""

    async def test_generated_web_article_passes_structure_gate(self) -> None:
        raw_document = make_raw_document()
        citation = make_citation(raw_document)
        context = build_default_context()

        fake_extraction = ExtractionOutput(
            fact="文部科学省は令和8年3月に生成AIパイロット校の公募を開始する検討会議の資料を公表した。",
            implication="現場教員は今後の審議会の動向を注視する必要がある。",
            discussion="対象校の具体的な選定基準はまだ示されていない。",
            score_impact=4,
            score_timeliness=5,
            score_controversy=3,
        )

        with patch(
            "src.processors.generator.generate_structured", AsyncMock(return_value=fake_extraction)
        ):
            draft, structure_raw = await generator.generate_web_article(
                raw_document, context, citation
            )

        # citation_idsはcitation自身のid(citations.idに対応)を参照する必要がある。
        # raw_document_idを誤って使っていたPhase4のバグの再発防止(Phase6で修正)。
        assert draft.key_points.citation_ids == [citation.id]
        assert structure_raw["citation_ids"] == [citation.id]

        harness_context = HarnessContext(
            draft=draft,
            body_text=structure_raw["body_markdown"],
            sources=[
                SourceExcerpt(
                    raw_document_id=raw_document.id,
                    text=raw_document.raw_text,
                    redistribution=RedistributionMode.FULL_ALLOWED,
                    quote_max_ratio=None,
                    attribution_required=True,
                )
            ],
            citations=[citation],
            structure_raw=structure_raw,
        )
        results = await run_gates(harness_context)
        g6 = next(r for r in results if r.gate.value == "G6")
        assert g6.passed is True, g6.reason
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is True, g1.reason

    async def test_generate_x_thread_produces_valid_structure(self) -> None:
        raw_document = make_raw_document()
        citation = make_citation(raw_document)
        context = build_default_context()

        fake_extraction = ExtractionOutput(
            fact="文部科学省は生成AIパイロット校の公募を開始する検討会議の資料を公表した。",
            implication="現場教員は動向を注視する必要がある。",
            discussion="選定基準はまだ示されていない。",
            score_impact=4, score_timeliness=5, score_controversy=3,
        )
        fake_thread = XThreadOutput(posts=["投稿1", "投稿2", "投稿3"])

        with (
            patch(
                "src.processors.generator.generate_structured",
                AsyncMock(side_effect=[fake_extraction, fake_thread]),
            ),
        ):
            draft, structure_raw = await generator.generate_x_thread(
                raw_document, context, citation
            )

        assert draft.format == DraftFormat.X_THREAD
        assert len(structure_raw["posts"]) == 3

    async def test_generate_youtube_script_produces_valid_structure(self) -> None:
        raw_document = make_raw_document()
        citation = make_citation(raw_document)
        context = build_default_context()

        fake_extraction = ExtractionOutput(
            fact="文部科学省は生成AIパイロット校の公募を開始する検討会議の資料を公表した。",
            implication="現場教員は動向を注視する必要がある。",
            discussion="選定基準はまだ示されていない。",
            score_impact=4, score_timeliness=5, score_controversy=3,
        )
        fake_script = YouTubeScriptOutput(script_text="台本本文", description_text="概要欄")

        with (
            patch(
                "src.processors.generator.generate_structured",
                AsyncMock(side_effect=[fake_extraction, fake_script]),
            ),
        ):
            draft, structure_raw = await generator.generate_youtube_script(
                raw_document, context, citation
            )

        assert draft.format == DraftFormat.YOUTUBE_SCRIPT
        assert structure_raw["script_text"] == "台本本文"
        assert structure_raw["description_text"] == "概要欄"


def test_context_bundle_defaults_are_empty_not_hardcoded() -> None:
    context: ContextBundle = build_default_context()
    assert context.curriculum_guidelines == []
    assert context.past_answers == []
    assert context.local_policies == []
    assert context.teacher_feedback == []
