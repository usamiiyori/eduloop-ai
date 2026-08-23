"""収集した一次情報（生データ）と SIST02 準拠の書誌メタデータ。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.source import FetchType, LicenseType, RedistributionMode


class PageOffset(BaseModel):
    """PDF抽出時のページ境界。引用時に「p.12」まで出せるよう文字オフセットを保持する。"""

    page_number: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class LicenseSnapshot(BaseModel):
    """取得時点のライセンス条件のスナップショット。sources.yaml の後日変更から過去生成物を守る。"""

    license: LicenseType
    attribution_required: bool
    redistribution: RedistributionMode
    quote_max_ratio: float | None = None


class RawDocument(BaseModel):
    """scrapers が取得した加工前の一次情報。processors 以降がこれを入力として消費する。"""

    id: UUID = Field(default_factory=uuid4)
    source_id: str
    fetch_type: FetchType
    url: str
    title: str
    published_at: datetime | None = Field(default=None, description="発行元の公開日時（判明時）")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = Field(description="HTML差分検知用のハッシュ（例: sha256）")
    raw_text: str
    page_offsets: list[PageOffset] = Field(default_factory=list, description="PDFのみ使用")
    license_snapshot: LicenseSnapshot


class Citation(BaseModel):
    """SIST02（科学技術情報流通技術基準）準拠の書誌情報。"""

    raw_document_id: UUID
    author_or_organization: str
    title: str
    container_title: str | None = Field(default=None, description="掲載媒体名（報告書・学会誌名）")
    publisher: str | None = None
    published_date: date | None = None
    url: str
    accessed_date: date = Field(default_factory=date.today)
    page: str | None = Field(default=None, description="例: 'p.12' や 'pp.12-14'")

    def to_sist02(self) -> str:
        """SIST02簡易フォーマットで整形した文字列を返す（G2ゲートのメタデータ完全性チェック対象）。"""
        parts = [self.author_or_organization, f"「{self.title}」"]
        if self.container_title:
            parts.append(self.container_title)
        if self.publisher:
            parts.append(self.publisher)
        if self.published_date:
            parts.append(self.published_date.isoformat())
        if self.page:
            parts.append(self.page)
        parts.append(f"{self.url} (参照 {self.accessed_date.isoformat()})")
        return ", ".join(parts)
