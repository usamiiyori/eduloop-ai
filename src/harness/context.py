"""ハーネス層の各ゲートが共有する入力コンテキスト。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.models.draft import Draft
from src.models.primary_source import Citation
from src.models.source import RedistributionMode

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass
class SourceExcerpt:
    """1つの一次情報（raw_document）から生成物が参照した範囲の情報。G1/G2/G4で使用する。"""

    raw_document_id: UUID
    text: str
    redistribution: RedistributionMode
    quote_max_ratio: float | None
    attribution_required: bool


@dataclass
class HarnessContext:
    """G1〜G6ゲートへの共通入力。フォーマット（Web記事/Xスレッド/YouTube台本）に依存しない形に正規化する。"""

    draft: Draft
    body_text: str  # 生成本文を1本の文字列に正規化したもの（G1/G2/G3/G4/G5が検査する対象）
    sources: list[SourceExcerpt]
    citations: list[Citation]
    structure_raw: dict[str, Any]  # G6が draft.format に応じたモデルへ model_validate する生データ
    past_draft_texts: list[str] = field(default_factory=list)  # G5比較対象（過去公開済み記事本文）
    pii_blocklist: list[str] = field(default_factory=list)  # G3追加検査する固有名詞（生徒名等）
    embed_texts: EmbedFn | None = field(
        default=None,
        metadata={
            "doc": (
                "G1の第二パス(意味的類似度)で使う埋め込み関数。未指定(None)ならG1は"
                "文字列一致/あいまい一致のみで判定する(フェイルクローズ、CLAUDE.md第1章)。"
            )
        },
    )
