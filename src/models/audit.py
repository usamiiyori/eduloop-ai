"""L2承認操作・自動処理の監査ログ。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuditAction(StrEnum):
    L1_GENERATED = "l1_generated"
    HARNESS_BLOCKED = "harness_blocked"
    L2_APPROVED = "l2_approved"
    L2_REJECTED = "l2_rejected"
    L2_REVISION_REQUESTED = "l2_revision_requested"
    PUBLISHED = "published"
    COST_LIMIT_EXCEEDED = "cost_limit_exceeded"


class AuditLogEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    actor: str = Field(description="'system' または承認者の識別子")
    action: AuditAction
    draft_id: UUID | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
