"""G1〜G6を実行し、失敗時は最大3回まで自己修復（再生成）ループを回すオーケストレーター。

3回失敗しても通過しない場合、生成物は破棄せず `needs_human` として人間のレビューキューに
残す（CLAUDE.md 第2章）。実際の再生成（regenerate）はプロンプト層の責務（Phase4）であり、
本モジュールはその呼び出しタイミングと再検証のみを担う。regenerate を渡さない場合は
1回のみ検証して結果を返す。

各ゲートは async def check(context) -> GateResult に統一している。G1が
HarnessContext.embed_texts経由でGemini埋め込みAPI(I/O)を呼びうるため（Phase4）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.harness import (
    g1_fact_verification,
    g2_citation_license,
    g3_pii,
    g4_assertion_risk,
    g5_duplicate,
    g6_structure,
)
from src.harness.context import HarnessContext
from src.models.harness import GateResult, HarnessRun

MAX_ATTEMPTS = 3

_GATES = (
    g1_fact_verification.check,
    g2_citation_license.check,
    g3_pii.check,
    g4_assertion_risk.check,
    g5_duplicate.check,
    g6_structure.check,
)

RegenerateFn = Callable[[HarnessContext, list[GateResult]], Awaitable[HarnessContext]]


async def run_gates(context: HarnessContext) -> list[GateResult]:
    """G1〜G6を順に実行する（1回分）。"""
    return [await gate(context) for gate in _GATES]


async def run_with_self_repair(
    context: HarnessContext, regenerate: RegenerateFn | None = None
) -> tuple[list[HarnessRun], bool]:
    """全ゲート通過するまで、最大 MAX_ATTEMPTS 回リトライする。

    戻り値: (各試行のHarnessRunのリスト, 最終的に全ゲート通過したか)。
    False の場合、呼び出し側は該当Draftのstatusを needs_human に更新すること。
    """
    runs: list[HarnessRun] = []
    current = context

    for attempt in range(1, MAX_ATTEMPTS + 1):
        results = await run_gates(current)
        run = HarnessRun(draft_id=current.draft.id, attempt=attempt, results=results)
        runs.append(run)

        if run.all_passed:
            return runs, True
        if attempt == MAX_ATTEMPTS or regenerate is None:
            break
        current = await regenerate(current, run.failed_gates)

    return runs, False
