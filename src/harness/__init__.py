"""ハーネス層。G1〜G6の自動検証ゲート（事実整合性・出典ライセンス・PII・断定リスク・重複・構造）と
自己修復リトライを提供する。"""

from __future__ import annotations

from src.harness.context import HarnessContext, SourceExcerpt
from src.harness.orchestrator import MAX_ATTEMPTS, run_gates, run_with_self_repair

__all__ = [
    "MAX_ATTEMPTS",
    "HarnessContext",
    "SourceExcerpt",
    "run_gates",
    "run_with_self_repair",
]
