"""G1 事実整合性ゲート。

生成文中の数値・事実文が原文（sources）に実在するかを検証する。まず機械的な文字列一致を試み、
一致しない場合のみ簡易的なあいまい一致（difflib）で補完し、それでも一致しない場合のみ
Gemini埋め込みによる意味的類似度判定（第二パス）を行う（docs/ARCHITECTURE.md 2.3節の方針:
文字列照合を第一ゲート、曖昧なケースのみ埋め込み判定でコスト最適化）。

context.embed_texts が未設定（GOOGLE_GENAI_API_KEY未設定など）の場合は第二パスをスキップし、
あいまい一致の結果のみで判定する（フェイルクローズ。CLAUDE.md 第1章「迷ったら出さない」）。
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

from src.harness.context import EmbedFn, HarnessContext
from src.models.harness import GateName, GateResult

# 依存方向は scrapers -> processors -> harness -> publishers の一方向（CLAUDE.md第3章）。
# 埋め込み関数の実装(Gemini API呼び出し)は processors 側が持ち、HarnessContext.embed_texts
# 経由で注入される。harness はコサイン類似度という純粋な数学関数のみをここに持つ。


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

_NUMBER_RE = re.compile(r"\d[\d,，.]*(?:%|％|人|校|億円|万円|円|件|回)?")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
_FUZZY_MATCH_THRESHOLD = 0.5
_FUZZY_WINDOW = 60
_SEMANTIC_MATCH_THRESHOLD = 0.80  # gemini-embedding-001での暫定値。運用しながら較正する
_SOURCE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？\n])")
# Gemini埋め込みAPIの batchEmbedContents は1回のリクエストにつき最大100件という制限がある
# （2026-08-23、実際のAPIエラー'BatchEmbedContentsRequest.requests: at most 100 requests
# can be in one batch'で確認）。長い原文で候補文がこれを超えないよう分割して呼び出す。
_EMBED_BATCH_LIMIT = 100


def _combined_source_text(context: HarnessContext) -> str:
    return "\n".join(s.text for s in context.sources)


def _best_fuzzy_ratio(sentence: str, source: str) -> float:
    if not sentence or not source:
        return 0.0
    best = 0.0
    step = max(1, _FUZZY_WINDOW // 2)
    for start in range(0, max(len(source) - _FUZZY_WINDOW, 0) + 1, step):
        chunk = source[start : start + _FUZZY_WINDOW]
        best = max(best, SequenceMatcher(None, sentence, chunk).ratio())
    return best


def _source_sentences(source: str) -> list[str]:
    return [s.strip() for s in _SOURCE_SENTENCE_SPLIT_RE.split(source) if s.strip()]


async def _semantic_verify(sentence: str, source: str, embed_texts: EmbedFn) -> float:
    candidates = _source_sentences(source)
    if not candidates:
        return 0.0

    best = 0.0
    chunk_size = _EMBED_BATCH_LIMIT - 1  # 先頭に sentence 自身を含めるため1件分空けておく
    for start in range(0, len(candidates), chunk_size):
        chunk = candidates[start : start + chunk_size]
        vectors = await embed_texts([sentence, *chunk])
        sentence_vec, chunk_vecs = vectors[0], vectors[1:]
        chunk_best = max(
            (_cosine_similarity(sentence_vec, v) for v in chunk_vecs), default=0.0
        )
        best = max(best, chunk_best)
    return best


async def check(context: HarnessContext) -> GateResult:
    source_text = _combined_source_text(context)
    failures: list[str] = []

    numbers: set[str] = set()
    for field_text in (
        context.draft.key_points.fact,
        context.draft.key_points.implication,
        context.draft.key_points.discussion,
    ):
        numbers |= set(_NUMBER_RE.findall(field_text))
    for number in sorted(numbers):
        if number not in source_text:
            failures.append(f"数値「{number}」が原文中に見つかりません")

    fact_sentences = _SENTENCE_SPLIT_RE.split(context.draft.key_points.fact)
    sentences = [s.strip() for s in fact_sentences if s.strip()]
    for sentence in sentences:
        if sentence in source_text:
            continue
        ratio = _best_fuzzy_ratio(sentence, source_text)
        if ratio >= _FUZZY_MATCH_THRESHOLD:
            continue

        if context.embed_texts is not None:
            similarity = await _semantic_verify(sentence, source_text, context.embed_texts)
            if similarity >= _SEMANTIC_MATCH_THRESHOLD:
                continue
            failures.append(
                f"Fact文「{sentence[:40]}」が原文と一致しません"
                f"(文字列類似度{ratio:.2f}, 意味的類似度{similarity:.2f})"
            )
        else:
            failures.append(
                f"Fact文「{sentence[:40]}」が原文と十分一致しません(類似度{ratio:.2f})"
            )

    if failures:
        return GateResult(
            gate=GateName.G1_FACT_VERIFICATION, passed=False, reason="; ".join(failures)
        )
    return GateResult(gate=GateName.G1_FACT_VERIFICATION, passed=True)
