"""L1: 収集(scrapers) → 下書き生成(processors) → 自動検証(harness) → Supabase永続化 →
承認待ちならSlackへレビュー依頼。GitHub Actions cron(毎時)から実行する。

Phase6スコープの意図的な簡略化（CLAUDE.md第0章ルール5: 推測でコードを書かない/判断は明示する）:
  - 自動生成はWeb記事のみを対象とする。ARCHITECTURE.md 8章で「Web記事は完全自動化可能な
    唯一のチャネル」と位置付けられているため。Xスレッド/YouTube台本は現時点では対象外とし、
    必要になった時点で別途Phaseとして追加する。
  - ネタ選定スコアが閾値未満のRawDocumentは、原文(raw_documents)のみ保存し、Draft化・harness
    検証は行わない（ARCHITECTURE.md 7章「閾値未満は記事化せず、DBに蓄積のみ」の実装として、
    reviewersキューを低スコア記事で埋めない設計にした）。
  - 1ソースあたり1回の実行で処理する新規記事数の上限(MAX_NEW_DOCS_PER_SOURCE)を設け、
    初回実行やRSS大量更新時のコスト急増を防ぐ。
"""

from __future__ import annotations

import asyncio

import structlog

from src.config import get_settings
from src.harness.context import EmbedFn, HarnessContext, SourceExcerpt
from src.harness.orchestrator import RegenerateFn, run_with_self_repair
from src.models.draft import Draft, DraftStatus
from src.models.harness import GateResult
from src.models.primary_source import Citation, RawDocument
from src.models.source import SourceConfig, load_sources
from src.processors import embeddings, generator
from src.processors.context import ContextBundle, build_default_context
from src.processors.scoring import passes_threshold
from src.publishers import email_notify
from src.scrapers import runner
from src.store import cost_log, drafts, raw_documents, source_health_store, system_control

logger = structlog.get_logger(__name__)

MAX_NEW_DOCS_PER_SOURCE = 5


async def _record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    await cost_log.record_usage(
        model=model, purpose="extraction", input_tokens=input_tokens, output_tokens=output_tokens
    )


async def _update_source_health(sources: list[SourceConfig], errors: dict[str, str]) -> None:
    for source in sources:
        if source.id in errors:
            health = await source_health_store.record_failure(source.id, errors[source.id])
            if health.consecutive_failures >= source_health_store.NOTIFY_THRESHOLD:
                await email_notify.send_email(
                    f"[EduLoop AI] 収集異常: {source.name}",
                    f"収集ソース「{source.name}」({source.id}) が"
                    f"{health.consecutive_failures}回連続で取得に失敗しています。\n"
                    f"直近のエラー: {health.last_error}",
                )
        else:
            await source_health_store.record_success(source.id)


def _dedup_new_documents(
    documents: list[RawDocument], known_hashes: dict[str, set[str]]
) -> list[RawDocument]:
    new_docs: list[RawDocument] = []
    seen_per_source: dict[str, int] = {}
    for doc in documents:
        known = known_hashes.get(doc.source_id, set())
        if doc.content_hash in known:
            continue
        count = seen_per_source.get(doc.source_id, 0)
        if count >= MAX_NEW_DOCS_PER_SOURCE:
            continue
        seen_per_source[doc.source_id] = count + 1
        new_docs.append(doc)
    return new_docs


def _make_regenerate(
    raw_document: RawDocument, context_bundle: ContextBundle, citation: Citation
) -> RegenerateFn:
    async def regenerate(current: HarnessContext, failed_gates: list[GateResult]) -> HarnessContext:
        reasons = [f"{r.gate.value}: {r.reason}" for r in failed_gates]
        new_draft, new_structure = await generator.generate_web_article(
            raw_document, context_bundle, citation, prior_failures=reasons, on_usage=_record_usage
        )
        # draft.id は自己修復ループ全体を通して同一に保つ(harness_runs.draft_idのFK先として
        # 最終的に1行だけdraftsに保存するため。CLAUDE.md第3章: drafts<->harness_runsの整合性)。
        new_draft.id = current.draft.id
        new_structure["draft_id"] = current.draft.id
        new_draft.retry_count = current.draft.retry_count + 1
        return HarnessContext(
            draft=new_draft,
            body_text=str(new_structure["body_markdown"]),
            sources=current.sources,
            citations=current.citations,
            structure_raw=new_structure,
            past_draft_texts=current.past_draft_texts,
            pii_blocklist=current.pii_blocklist,
            embed_texts=current.embed_texts,
        )

    return regenerate


async def _process_document(
    source: SourceConfig,
    raw_document: RawDocument,
    context_bundle: ContextBundle,
    past_draft_texts: list[str],
    embed_fn: EmbedFn | None,
) -> None:
    await raw_documents.save_raw_document(raw_document)

    citation = Citation(
        raw_document_id=raw_document.id,
        author_or_organization=source.name,
        title=raw_document.title,
        url=raw_document.url,
    )

    draft, structure_raw = await generator.generate_web_article(
        raw_document, context_bundle, citation, on_usage=_record_usage
    )

    if not passes_threshold(draft):
        logger.info(
            "draft_below_threshold_archived_raw_only",
            source_id=source.id,
            score_total=draft.score_total,
        )
        return

    await raw_documents.save_citation(citation)

    harness_context = HarnessContext(
        draft=draft,
        body_text=str(structure_raw["body_markdown"]),
        sources=[
            SourceExcerpt(
                raw_document_id=raw_document.id,
                text=raw_document.raw_text,
                redistribution=source.redistribution,
                quote_max_ratio=source.quote_max_ratio,
                attribution_required=source.attribution_required,
            )
        ],
        citations=[citation],
        structure_raw=structure_raw,
        past_draft_texts=past_draft_texts,
        pii_blocklist=[],
        embed_texts=embed_fn,
    )

    regenerate = _make_regenerate(raw_document, context_bundle, citation)
    runs, all_passed, final_context = await run_with_self_repair(harness_context, regenerate)

    final_draft: Draft = final_context.draft
    final_draft.status = DraftStatus.DRAFT if all_passed else DraftStatus.NEEDS_HUMAN

    await drafts.save_draft(final_draft)
    await drafts.save_format_content(final_draft.format, final_context.structure_raw)
    await drafts.save_harness_runs(runs)

    # 記事ごとの即時メールは送らない。レビュー依頼は1日1回、夕方に
    # src/pipeline/review_digest.py がまとめて届ける
    # (2026-08-23、オーナーの希望により逐次通知から日次まとめ通知に変更)。
    if all_passed:
        logger.info(
            "draft_ready_for_review", title=raw_document.title, score=final_draft.score_total
        )
    else:
        logger.warning("draft_needs_human", title=raw_document.title)


async def run() -> None:
    paused, reason = await system_control.is_paused()
    if paused:
        logger.warning("l1_skipped_paused", reason=reason)
        return

    limit = _daily_cost_limit()
    spent_today = await cost_log.today_total_usd()
    if spent_today >= limit:
        logger.warning("l1_skipped_cost_limit", spent_today=spent_today, limit=limit)
        await email_notify.send_email(
            "[EduLoop AI] コスト上限のためL1をスキップしました",
            f"本日のLLM推定コストが上限(${limit:.2f})に達したため、"
            f"L1収集をスキップしました。現在の推定コスト: ${spent_today:.2f}",
        )
        return

    sources = load_sources()
    run_result = await runner.run_sources(sources)
    await _update_source_health(sources, run_result.errors)

    known_hashes = {
        source.id: await raw_documents.existing_content_hashes(source.id) for source in sources
    }
    new_documents = _dedup_new_documents(run_result.documents, known_hashes)
    if not new_documents:
        logger.info("l1_no_new_documents")
        return

    context_bundle = build_default_context()
    past_draft_texts = await drafts.recent_published_web_article_bodies()
    embed_fn = embeddings.embed_texts if _google_api_key_set() else None
    source_by_id = {s.id: s for s in sources}

    for raw_document in new_documents:
        spent_today = await cost_log.today_total_usd()
        if spent_today >= limit:
            logger.warning("l1_stopped_mid_run_cost_limit", spent_today=spent_today)
            await email_notify.send_email(
                "[EduLoop AI] コスト上限のため処理を中断しました",
                f"本日のLLM推定コストが上限(${limit:.2f})に達したため、"
                "残りの記事の処理を中断しました。次回実行時に続きを処理します。",
            )
            break
        source = source_by_id[raw_document.source_id]
        try:
            await _process_document(
                source, raw_document, context_bundle, past_draft_texts, embed_fn
            )
        except Exception:  # noqa: BLE001 — 1件の失敗が他の記事の処理を止めないようにする
            logger.exception("l1_process_document_failed", raw_document_id=str(raw_document.id))


def _daily_cost_limit() -> float:
    return get_settings().llm_daily_cost_limit_usd


def _google_api_key_set() -> bool:
    return bool(get_settings().google_genai_api_key)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
