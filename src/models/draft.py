"""プロンプト層の出力（論点抽出）と3配信形式（Web記事/Xスレッド/YouTube台本）の構造化モデル。"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class DraftFormat(StrEnum):
    WEB_ARTICLE = "web_article"
    X_THREAD = "x_thread"
    YOUTUBE_SCRIPT = "youtube_script"


class DraftStatus(StrEnum):
    """L1〜L2ループの状態遷移。needs_human は harness を3回失敗した生成物（破棄しない）。"""

    DRAFT = "draft"
    NEEDS_HUMAN = "needs_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class KeyPoints(BaseModel):
    """プロンプト層の抽出フォーマット固定4観点。原文に紐づかない主張はG1で弾かれる。"""

    fact: str = Field(description="原文に明記された事実・数値。丸め・概算は禁止")
    implication: str = Field(description="教育現場への含意。AIによる解釈である旨を含む")
    discussion: str = Field(description="論点・賛否・未解決課題")
    citation_ids: list[UUID] = Field(default_factory=list)


class Draft(BaseModel):
    """全フォーマット共通の親モデル。ネタ選定スコアリングと状態管理を持つ。"""

    id: UUID = Field(default_factory=uuid4)
    raw_document_ids: list[UUID] = Field(min_length=1)
    format: DraftFormat
    status: DraftStatus = DraftStatus.DRAFT
    key_points: KeyPoints
    score_impact: int = Field(ge=1, le=5, description="現場インパクト")
    score_timeliness: int = Field(ge=1, le=5, description="速報性")
    score_controversy: int = Field(ge=1, le=5, description="議論の余地")
    retry_count: int = Field(default=0, ge=0, le=3)

    @property
    def score_total(self) -> int:
        """score = 現場インパクト × 速報性 × 議論の余地（docs/ARCHITECTURE.md 第7章）。"""
        return self.score_impact * self.score_timeliness * self.score_controversy


class WebArticle(BaseModel):
    """Web記事Markdown。①事実②含意③論点④出典の4部構成を必須とする（G6構造ゲート対象）。"""

    draft_id: UUID
    title: str
    slug: str
    body_markdown: str
    citation_ids: list[UUID] = Field(min_length=1, description="出典なしの記事は禁止")
    utm_campaign: str

    @field_validator("body_markdown")
    @classmethod
    def _require_four_sections(cls, v: str) -> str:
        required = ["事実", "含意", "論点", "出典"]
        missing = [s for s in required if s not in v]
        if missing:
            raise ValueError(f"Web記事は4部構成が必須です。欠けているセクション: {missing}")
        return v


class XPost(BaseModel):
    order_index: int = Field(ge=0)
    text: str = Field(max_length=140)


class XThread(BaseModel):
    """Xスレッド。140字×3〜5連（G6構造ゲート対象）。"""

    draft_id: UUID
    posts: list[XPost] = Field(min_length=3, max_length=5)

    @field_validator("posts")
    @classmethod
    def _ordered_from_zero(cls, v: list[XPost]) -> list[XPost]:
        order = sorted(p.order_index for p in v)
        if order != list(range(len(v))):
            raise ValueError("posts の order_index は 0 から連番で指定してください")
        return v


class YouTubeScript(BaseModel):
    """YouTube台本。NotebookLM等での音声化を想定し読み上げやすい文体で出力する。"""

    draft_id: UUID
    script_text: str
    description_text: str = Field(description="概要欄テキスト")
