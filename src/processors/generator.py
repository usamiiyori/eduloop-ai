"""生成層のオーケストレーション。RawDocument→論点抽出→3形式（Web記事/Xスレッド/YouTube台本）の
組み立てまでを行う。実際のLLM呼び出しは src/processors/llm_client.py に委譲する。

Web記事の本文は、LLMの抽出結果（Fact/Implication/Discussion）からテンプレートで機械的に
組み立てる（LLMに直接Markdown全体を生成させない）。理由: ①4部構成をハーネスG6ゲートで
確実に満たせる ②各セクションの文言がFact/Implication/Discussionの抽出結果と食い違う
（ハルシネーションで内容が変わる）リスクを避けられるため。
"""

from __future__ import annotations

from uuid import UUID

from src.models.draft import Draft, DraftFormat, KeyPoints
from src.models.primary_source import Citation, RawDocument
from src.processors import prompt_builder
from src.processors.context import ContextBundle
from src.processors.llm_client import UsageCallback, generate_structured
from src.processors.schemas import ExtractionOutput, XThreadOutput, YouTubeScriptOutput


def _slug_for(raw_document: RawDocument) -> str:
    return f"{raw_document.source_id}-{raw_document.content_hash[:8]}"


def assemble_web_article_markdown(
    extraction: ExtractionOutput, context: ContextBundle, citation_label: str
) -> str:
    sections = context.editorial_voice.required_sections
    return (
        f"## {sections[0]}\n{extraction.fact}\n\n"
        f"## {sections[1]}\n{extraction.implication}\n\n"
        f"## {sections[2]}\n{extraction.discussion}\n\n"
        f"## {sections[3]}\n{citation_label}\n"
    )


async def extract_key_points(
    raw_document: RawDocument,
    context: ContextBundle,
    *,
    prior_failures: list[str] | None = None,
    on_usage: UsageCallback | None = None,
) -> ExtractionOutput:
    prompt = prompt_builder.build_extraction_prompt(
        raw_document, context, prior_failures=prior_failures
    )
    return await generate_structured(prompt, ExtractionOutput, on_usage=on_usage)


def _build_draft(
    raw_document: RawDocument,
    extraction: ExtractionOutput,
    format_: DraftFormat,
    citation_id: UUID,
) -> Draft:
    return Draft(
        raw_document_ids=[raw_document.id],
        format=format_,
        key_points=KeyPoints(
            fact=extraction.fact,
            implication=extraction.implication,
            discussion=extraction.discussion,
            citation_ids=[citation_id],
        ),
        score_impact=extraction.score_impact,
        score_timeliness=extraction.score_timeliness,
        score_controversy=extraction.score_controversy,
    )


async def generate_web_article(
    raw_document: RawDocument,
    context: ContextBundle,
    citation: Citation,
    *,
    prior_failures: list[str] | None = None,
    on_usage: UsageCallback | None = None,
) -> tuple[Draft, dict[str, object]]:
    extraction = await extract_key_points(
        raw_document, context, prior_failures=prior_failures, on_usage=on_usage
    )
    draft = _build_draft(
        raw_document, extraction, DraftFormat.WEB_ARTICLE, citation.id
    )
    body_markdown = assemble_web_article_markdown(extraction, context, citation.to_sist02())
    structure_raw: dict[str, object] = {
        "draft_id": draft.id,
        "title": raw_document.title,
        "slug": _slug_for(raw_document),
        "body_markdown": body_markdown,
        "citation_ids": [citation.id],
        "utm_campaign": _slug_for(raw_document),
    }
    return draft, structure_raw


async def generate_x_thread(
    raw_document: RawDocument,
    context: ContextBundle,
    citation: Citation,
    *,
    on_usage: UsageCallback | None = None,
) -> tuple[Draft, dict[str, object]]:
    extraction = await extract_key_points(raw_document, context, on_usage=on_usage)
    draft = _build_draft(raw_document, extraction, DraftFormat.X_THREAD, citation.id)
    prompt = prompt_builder.build_x_thread_prompt(extraction, context)
    thread = await generate_structured(prompt, XThreadOutput, on_usage=on_usage)
    structure_raw: dict[str, object] = {
        "draft_id": draft.id,
        "posts": [{"order_index": i, "text": t} for i, t in enumerate(thread.posts)],
    }
    return draft, structure_raw


async def generate_youtube_script(
    raw_document: RawDocument,
    context: ContextBundle,
    citation: Citation,
    *,
    on_usage: UsageCallback | None = None,
) -> tuple[Draft, dict[str, object]]:
    extraction = await extract_key_points(raw_document, context, on_usage=on_usage)
    draft = _build_draft(
        raw_document, extraction, DraftFormat.YOUTUBE_SCRIPT, citation.id
    )
    prompt = prompt_builder.build_youtube_script_prompt(extraction, context)
    script = await generate_structured(prompt, YouTubeScriptOutput, on_usage=on_usage)
    structure_raw: dict[str, object] = {
        "draft_id": draft.id,
        "script_text": script.script_text,
        "description_text": script.description_text,
    }
    return draft, structure_raw
