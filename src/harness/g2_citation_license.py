"""G2 出典・ライセンスゲート。

出典(Citation)の有無、および config/sources.yaml のライセンス台帳が定める再配布ルール
（full_allowed/summary_only/quote_only）への違反を機械的に検査する（CLAUDE.md 第4章）。
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.harness.context import HarnessContext
from src.models.harness import GateName, GateResult
from src.models.source import RedistributionMode

_MIN_QUOTE_BLOCK = 15  # これ未満の一致は偶然の一致とみなし「引用」に数えない
_SUMMARY_ONLY_BLOCK_LIMIT = 30  # summary_only で許容する最大連続一致文字数


def _quote_ratio(body: str, source: str) -> float:
    if not source:
        return 0.0
    matcher = SequenceMatcher(None, body, source, autojunk=False)
    matched = sum(b.size for b in matcher.get_matching_blocks() if b.size >= _MIN_QUOTE_BLOCK)
    return matched / len(source)


def _longest_verbatim_block(body: str, source: str) -> int:
    matcher = SequenceMatcher(None, body, source, autojunk=False)
    return max((b.size for b in matcher.get_matching_blocks()), default=0)


async def check(context: HarnessContext) -> GateResult:
    failures: list[str] = []

    if not context.citations:
        failures.append("出典(Citation)が1件も紐づいていません")

    for source in context.sources:
        if source.attribution_required and not context.citations:
            failures.append(f"ソース{source.raw_document_id}: 出典明記が必須ですが出典がありません")

        if source.redistribution == RedistributionMode.QUOTE_ONLY:
            ratio = _quote_ratio(context.body_text, source.text)
            limit = source.quote_max_ratio or 0.0
            if ratio > limit:
                failures.append(
                    f"ソース{source.raw_document_id}: 引用比率{ratio:.1%}が上限{limit:.0%}を超過"
                    "(quote_only)"
                )
        elif source.redistribution == RedistributionMode.SUMMARY_ONLY:
            longest = _longest_verbatim_block(context.body_text, source.text)
            if longest >= _SUMMARY_ONLY_BLOCK_LIMIT:
                failures.append(
                    f"ソース{source.raw_document_id}: summary_onlyだが{longest}文字の"
                    "逐語引用を検出しました"
                )

    if failures:
        return GateResult(
            gate=GateName.G2_CITATION_LICENSE, passed=False, reason="; ".join(failures)
        )
    return GateResult(gate=GateName.G2_CITATION_LICENSE, passed=True)
