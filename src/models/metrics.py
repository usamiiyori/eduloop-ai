"""収益モデルKPI計測（docs/ARCHITECTURE.md 第4章）。推測せず計測可能な形でDBに持たせる。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DataSource(StrEnum):
    """指標の取得経路。API取得が使えないチャネル（note等）は手動入力にフォールバックする。"""

    MANUAL = "manual"
    API = "api"


class PostMetric(BaseModel):
    """X/YouTube等の集客指標。"""

    id: UUID = Field(default_factory=uuid4)
    draft_id: UUID
    channel: str = Field(description="例: 'x', 'youtube'")
    impressions: int = Field(default=0, ge=0)
    profile_clicks: int = Field(default=0, ge=0)
    data_source: DataSource
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LinkClick(BaseModel):
    """UTM付きリンク経由の回遊計測。"""

    id: UUID = Field(default_factory=uuid4)
    draft_id: UUID
    utm_campaign: str
    url: str
    referrer: str | None = None
    clicked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversion(BaseModel):
    """note有料版・メンバーシップ等の収益コンバージョン。note経由はAPIが無いため手動入力が前提。"""

    id: UUID = Field(default_factory=uuid4)
    draft_id: UUID
    channel: str = Field(description="例: 'note'")
    amount_jpy: int = Field(ge=0)
    data_source: DataSource
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InboundLead(BaseModel):
    """被言及・登壇依頼・問い合わせ等の信用指標。"""

    id: UUID = Field(default_factory=uuid4)
    name: str
    contact: str
    message: str
    source_channel: str = Field(description="例: '問い合わせフォーム', 'X DM'")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceHealth(BaseModel):
    """収集ソースの疎通状況。3回連続失敗でオーナーに通知する判定に使う。"""

    source_id: str
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    last_error: str = ""
