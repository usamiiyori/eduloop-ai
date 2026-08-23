"""G1〜G6 検証ゲートの結果モデル（判定ロジック自体は Phase 3 で src/harness/ に実装）。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GateName(StrEnum):
    G1_FACT_VERIFICATION = "G1"
    G2_CITATION_LICENSE = "G2"
    G3_PII = "G3"
    G4_ASSERTION_RISK = "G4"
    G5_DUPLICATE = "G5"
    G6_STRUCTURE = "G6"


class GateResult(BaseModel):
    """1ゲート1回分の判定結果。"""

    gate: GateName
    passed: bool
    reason: str = Field(default="", description="失敗時は再生成プロンプトに再注入される")


class HarnessRun(BaseModel):
    """1生成物に対する1回の全ゲート実行結果。"""

    id: UUID = Field(default_factory=uuid4)
    draft_id: UUID
    attempt: int = Field(ge=1, le=3)
    results: list[GateResult]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed_gates(self) -> list[GateResult]:
        return [r for r in self.results if not r.passed]
