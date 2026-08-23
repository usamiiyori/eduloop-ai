"""ハーネス層(G1〜G6)のテスト。各ゲートについて「正常系は通す」「意図的に壊れた入力はブロックする」
の両方を検証する。事実整合性・PII・断定リスクは特に、壊れた入力を検出できることを必須で確認する
(CLAUDE.md 第10章)。
"""

from __future__ import annotations

from uuid import uuid4

from src.harness.context import EmbedFn, HarnessContext, SourceExcerpt
from src.harness.orchestrator import run_gates, run_with_self_repair
from src.models.draft import Draft, DraftFormat, KeyPoints
from src.models.primary_source import Citation
from src.models.source import RedistributionMode

SOURCE_TEXT = (
    "文部科学省は令和8年3月に生成AIパイロット校の公募を開始する検討会議の資料を公表した。"
    "対象校は全国で20校程度を想定しており、詳細は今後の審議会で議論される予定である。"
)


def make_citation() -> Citation:
    return Citation(
        raw_document_id=uuid4(),
        author_or_organization="文部科学省",
        title="生成AIパイロット校公募資料",
        url="https://www.mext.go.jp/example.pdf",
    )


def make_source_excerpt(**overrides: object) -> SourceExcerpt:
    base: dict[str, object] = {
        "raw_document_id": uuid4(),
        "text": SOURCE_TEXT,
        "redistribution": RedistributionMode.FULL_ALLOWED,
        "quote_max_ratio": None,
        "attribution_required": True,
    }
    base.update(overrides)
    return SourceExcerpt(**base)  # type: ignore[arg-type]


def make_context(
    *,
    fact: str = (
        "文部科学省は令和8年3月に生成AIパイロット校の公募を開始する検討会議の資料を公表した。"
    ),
    implication: str = "現場教員は今後の審議会の動向を注視する必要がある(AIによる解釈)。",
    discussion: str = "対象校の具体的な選定基準はまだ示されていない。",
    body_text: str | None = None,
    sources: list[SourceExcerpt] | None = None,
    citations: list[Citation] | None = None,
    past_draft_texts: list[str] | None = None,
    pii_blocklist: list[str] | None = None,
    embed_texts: EmbedFn | None = None,
) -> HarnessContext:
    draft = Draft(
        raw_document_ids=[uuid4()],
        format=DraftFormat.WEB_ARTICLE,
        key_points=KeyPoints(fact=fact, implication=implication, discussion=discussion),
        score_impact=4,
        score_timeliness=5,
        score_controversy=3,
    )
    default_body = f"{fact}\n{implication}\n{discussion}\n出典: 文部科学省"
    resolved_body = body_text if body_text is not None else default_body
    resolved_citations = citations if citations is not None else [make_citation()]
    structure_raw = {
        "draft_id": draft.id,
        "title": "生成AIパイロット校、公募開始へ",
        "slug": "genai-pilot-school-boshu",
        "body_markdown": (
            f"## 事実\n{fact}\n## 含意\n{implication}\n## 論点\n{discussion}\n## 出典\n文部科学省"
        ),
        "citation_ids": [c.raw_document_id for c in resolved_citations] or [uuid4()],
        "utm_campaign": "genai_pilot",
    }
    return HarnessContext(
        draft=draft,
        body_text=resolved_body,
        sources=sources if sources is not None else [make_source_excerpt()],
        citations=resolved_citations,
        structure_raw=structure_raw,
        past_draft_texts=past_draft_texts or [],
        pii_blocklist=pii_blocklist or [],
        embed_texts=embed_texts,
    )


class TestFullyValidDraftPasses:
    async def test_all_gates_pass(self) -> None:
        context = make_context()
        results = await run_gates(context)
        failed = [r for r in results if not r.passed]
        assert not failed, f"想定外の失敗: {[(r.gate, r.reason) for r in failed]}"


class TestG1FactVerification:
    async def test_blocks_fabricated_number(self) -> None:
        context = make_context(
            fact="文部科学省は生成AIパイロット校を全国で40校指定することを公表した。"
        )
        results = await run_gates(context)
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is False
        assert "40校" in g1.reason

    async def test_blocks_unrelated_fact_sentence(self) -> None:
        context = make_context(
            fact="生成AIは自治体の全予算をすでに置き換えたと専門家は評価している。"
        )
        results = await run_gates(context)
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is False

    async def test_paraphrase_blocked_without_embedder(self) -> None:
        """埋め込み関数が未設定(APIキー未設定相当)の場合、正しい言い換えも文字列的に
        遠ければブロックされる(フェイルクローズ)。これはPhase3時点の既知の制約。"""
        context = make_context(
            fact=(
                "文科省が来年度、AIを使った授業のパイロット事業を全国約20の学校で"
                "スタートさせる方針を固めたことが分かった。"
            ),
            embed_texts=None,
        )
        results = await run_gates(context)
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is False

    async def test_paraphrase_passes_with_semantic_embedder(self) -> None:
        """埋め込み関数を注入すると、文字列は違っても意味的に一致する言い換えは通過する
        (Phase4: GOOGLE_GENAI_API_KEY設定後の第二パス)。"""

        async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
            # 1つ目(生成文)と、原文中の対応文にだけ高い類似度を持つベクトルを返す偽実装。
            vectors = []
            for t in texts:
                if "パイロット事業" in t or "検討会議の資料を公表した" in t:
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

        context = make_context(
            fact=(
                "文科省が来年度、AIを使った授業のパイロット事業を全国約20の学校で"
                "スタートさせる方針を固めたことが分かった。"
            ),
            embed_texts=fake_embed_texts,
        )
        results = await run_gates(context)
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is True, g1.reason

    async def test_still_blocked_with_embedder_when_semantically_unrelated(self) -> None:
        async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] if i == 0 else [0.0, 1.0] for i in range(len(texts))]

        context = make_context(
            fact="生成AIは自治体の全予算をすでに置き換えたと専門家は評価している。",
            embed_texts=fake_embed_texts,
        )
        results = await run_gates(context)
        g1 = next(r for r in results if r.gate.value == "G1")
        assert g1.passed is False
        assert "意味的類似度" in g1.reason


class TestG2CitationLicense:
    async def test_blocks_missing_citation(self) -> None:
        context = make_context(citations=[])
        results = await run_gates(context)
        g2 = next(r for r in results if r.gate.value == "G2")
        assert g2.passed is False
        assert "出典" in g2.reason

    async def test_blocks_quote_ratio_over_limit(self) -> None:
        quote_only_source = make_source_excerpt(
            redistribution=RedistributionMode.QUOTE_ONLY, quote_max_ratio=0.1
        )
        # body_textを原文とほぼ同一にして引用比率を上限超過させる
        context = make_context(body_text=SOURCE_TEXT + SOURCE_TEXT, sources=[quote_only_source])
        results = await run_gates(context)
        g2 = next(r for r in results if r.gate.value == "G2")
        assert g2.passed is False
        assert "引用比率" in g2.reason

    async def test_blocks_summary_only_verbatim_quote(self) -> None:
        summary_only_source = make_source_excerpt(redistribution=RedistributionMode.SUMMARY_ONLY)
        context = make_context(body_text=SOURCE_TEXT, sources=[summary_only_source])
        results = await run_gates(context)
        g2 = next(r for r in results if r.gate.value == "G2")
        assert g2.passed is False
        assert "逐語引用" in g2.reason


class TestG3Pii:
    async def test_blocks_email_address(self) -> None:
        context = make_context(
            discussion="詳細はtanaka-taro@example-school.ed.jpまでご連絡くださいとのことです。"
        )
        results = await run_gates(context)
        g3 = next(r for r in results if r.gate.value == "G3")
        assert g3.passed is False
        assert "メールアドレス" in g3.reason

    async def test_blocks_blocklisted_name(self) -> None:
        context = make_context(
            discussion="この施策については山田花子教諭が校内で説明会を行った。",
            pii_blocklist=["山田花子"],
        )
        results = await run_gates(context)
        g3 = next(r for r in results if r.gate.value == "G3")
        assert g3.passed is False
        assert "山田花子" in g3.reason


class TestG4AssertionRisk:
    async def test_blocks_overclaiming_early_stage_source(self) -> None:
        early_stage_source = make_source_excerpt(
            text="文部科学省の検討会議は生成AIパイロット校の公募について審議中であり、詳細は未定である。"
        )
        context = make_context(
            fact="文部科学省の検討会議は生成AIパイロット校の公募について審議中であり、詳細は未定である。",
            discussion="生成AIパイロット校の実施が決定した。",
            sources=[early_stage_source],
        )
        results = await run_gates(context)
        g4 = next(r for r in results if r.gate.value == "G4")
        assert g4.passed is False
        assert "段階" in g4.reason

    async def test_allows_assertion_when_source_confirms_late_stage(self) -> None:
        late_stage_source = make_source_excerpt(
            text="文部科学省は生成AIパイロット校事業の実施要領を告示し、事業が正式決定した。"
        )
        context = make_context(
            fact="文部科学省は生成AIパイロット校事業の実施要領を告示し、事業が正式決定した。",
            discussion="事業が正式決定したことで各校は準備を進める必要がある。",
            sources=[late_stage_source],
        )
        results = await run_gates(context)
        g4 = next(r for r in results if r.gate.value == "G4")
        assert g4.passed is True


class TestG5Duplicate:
    async def test_blocks_near_identical_past_article(self) -> None:
        body = "文部科学省が生成AIパイロット校の公募を開始した件を現場目線で解説する記事です。"
        context = make_context(body_text=body, past_draft_texts=[body])
        results = await run_gates(context)
        g5 = next(r for r in results if r.gate.value == "G5")
        assert g5.passed is False
        assert "続報" in g5.reason


class TestG6Structure:
    async def test_blocks_web_article_missing_section(self) -> None:
        context = make_context()
        context.structure_raw["body_markdown"] = "事実だけ書いてあって他のセクションがない本文"
        results = await run_gates(context)
        g6 = next(r for r in results if r.gate.value == "G6")
        assert g6.passed is False

    async def test_blocks_x_thread_too_many_posts(self) -> None:
        context = make_context()
        context.draft.format = DraftFormat.X_THREAD
        context.structure_raw = {
            "draft_id": context.draft.id,
            "posts": [{"order_index": i, "text": f"投稿{i}"} for i in range(6)],
        }
        results = await run_gates(context)
        g6 = next(r for r in results if r.gate.value == "G6")
        assert g6.passed is False


class TestSelfRepairLoop:
    async def test_regenerates_until_pii_removed(self) -> None:
        bad_context = make_context(
            discussion="この施策については山田花子教諭が校内で説明会を行った。",
            pii_blocklist=["山田花子"],
        )
        attempts_seen: list[int] = []

        async def regenerate(context: HarnessContext, failed):  # noqa: ANN001, ANN201
            attempts_seen.append(len(attempts_seen) + 1)
            fixed = make_context(
                discussion="この施策については学校の教員が校内で説明会を行った。",
                pii_blocklist=["山田花子"],
            )
            return fixed

        runs, passed, _final = await run_with_self_repair(bad_context, regenerate=regenerate)

        assert passed is True
        assert len(runs) == 2  # 1回目失敗 → 再生成 → 2回目成功
        assert runs[0].all_passed is False
        assert runs[1].all_passed is True
        assert attempts_seen == [1]

    async def test_marks_needs_human_after_max_attempts(self) -> None:
        bad_context = make_context(
            discussion="この施策については山田花子教諭が校内で説明会を行った。",
            pii_blocklist=["山田花子"],
        )

        async def regenerate_that_never_fixes(context: HarnessContext, failed):  # noqa: ANN001, ANN201
            return bad_context

        runs, passed, _final = await run_with_self_repair(
            bad_context, regenerate=regenerate_that_never_fixes
        )

        assert passed is False
        assert len(runs) == 3
        assert all(not r.all_passed for r in runs)

    async def test_single_pass_without_regenerate_callback(self) -> None:
        context = make_context()
        runs, passed, _final = await run_with_self_repair(context, regenerate=None)
        assert passed is True
        assert len(runs) == 1
