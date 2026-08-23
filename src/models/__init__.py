"""Pydantic v2 モデル群。一次情報・引用メタデータ(SIST02準拠)・教員コメント・監査ログを定義する。"""

from __future__ import annotations

from src.models.audit import AuditAction, AuditLogEntry
from src.models.community import TeacherComment, TeacherProfile
from src.models.draft import (
    Draft,
    DraftFormat,
    DraftStatus,
    KeyPoints,
    WebArticle,
    XPost,
    XThread,
    YouTubeScript,
)
from src.models.harness import GateName, GateResult, HarnessRun
from src.models.metrics import (
    Conversion,
    DataSource,
    InboundLead,
    LinkClick,
    PostMetric,
    SourceHealth,
)
from src.models.primary_source import Citation, LicenseSnapshot, PageOffset, RawDocument
from src.models.source import (
    FetchType,
    LicenseType,
    RedistributionMode,
    SourceAxis,
    SourceConfig,
    load_sources,
)

__all__ = [
    "AuditAction",
    "AuditLogEntry",
    "Citation",
    "Conversion",
    "DataSource",
    "Draft",
    "DraftFormat",
    "DraftStatus",
    "FetchType",
    "GateName",
    "GateResult",
    "HarnessRun",
    "InboundLead",
    "KeyPoints",
    "LicenseSnapshot",
    "LicenseType",
    "LinkClick",
    "PageOffset",
    "PostMetric",
    "RawDocument",
    "RedistributionMode",
    "SourceAxis",
    "SourceConfig",
    "SourceHealth",
    "TeacherComment",
    "TeacherProfile",
    "WebArticle",
    "XPost",
    "XThread",
    "YouTubeScript",
    "load_sources",
]
