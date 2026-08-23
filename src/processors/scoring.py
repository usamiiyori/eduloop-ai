"""ネタ選定スコアリング（docs/ARCHITECTURE.md 第7章）。
score = 現場インパクト × 速報性 × 議論の余地。閾値未満は記事化せずDBに蓄積のみとする。
"""

from __future__ import annotations

from src.config import get_settings
from src.models.draft import Draft


def passes_threshold(draft: Draft, threshold: int | None = None) -> bool:
    limit = threshold if threshold is not None else get_settings().article_score_threshold
    return draft.score_total >= limit
