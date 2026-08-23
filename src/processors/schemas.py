"""LLMへの構造化出力要求(response_schema)に使うPydanticモデル。src/models/draft.py の
KeyPoints等とは別に定義する（LLM出力の生の受け皿であり、harnessに渡す前にvalidation・
組み立てを行うための中間表現のため）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionOutput(BaseModel):
    """プロンプト層の論点抽出結果（Fact/Implication/Discussion）とネタ選定スコア。"""

    fact: str = Field(description="原文に明記された事実・数値のみ。丸め・概算は禁止")
    implication: str = Field(description="教育現場への含意。AIによる解釈である旨を含む")
    discussion: str = Field(description="論点・賛否・未解決課題")
    score_impact: int = Field(ge=1, le=5, description="現場インパクト")
    score_timeliness: int = Field(ge=1, le=5, description="速報性")
    score_controversy: int = Field(ge=1, le=5, description="議論の余地")


class XThreadOutput(BaseModel):
    posts: list[str] = Field(min_length=3, max_length=5, description="140字以内×3〜5連")


class YouTubeScriptOutput(BaseModel):
    script_text: str = Field(description="読み上げやすい文体の台本本文")
    description_text: str = Field(description="概要欄テキスト")
