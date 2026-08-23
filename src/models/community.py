"""L3知見還元で使う教員コミュニティ機能の最小モデル（将来拡張見込み）。個人特定情報は持たない。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TeacherProfile(BaseModel):
    """Supabase auth.users と1対1で紐づく公開プロフィール。学校名等の特定情報は含めない。"""

    id: UUID = Field(default_factory=uuid4, description="auth.users.id と同一")
    display_name: str
    region: str | None = Field(default=None, description="例: '愛知県'。市区町村・学校名は持たない")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TeacherComment(BaseModel):
    """公開記事への実践知コメント。L3でコンテキスト層への注入元として集約される。"""

    id: UUID = Field(default_factory=uuid4)
    teacher_id: UUID
    draft_id: UUID
    comment: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
