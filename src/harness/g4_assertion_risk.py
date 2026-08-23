"""G4 断定リスクゲート（最重要）。

政策文書の段階（検討中/中間まとめ/答申/告示/施行）を誤読した断定表現を検出する。Phase3時点では
GOOGLE_GENAI_API_KEY未設定のためLLM-as-a-Judgeは使えず、キーワードベースの規則的判定を第一段
として実装する。原文が早期段階（検討中/審議中/素案等）を示す語のみを含み、かつ公布・施行等の
後期段階を示す語を含まないにもかかわらず、生成文に強い断定表現があれば「段階の誤読の疑い」として
差し戻す。APIキー設定後（Phase4/6）は本モジュールをLLM-as-a-Judgeによる意味的判定で置き換える
か、本モジュールを一次フィルタとして併用する。判定に迷う場合は差し戻す（CLAUDE.md 第1章）。
"""

from __future__ import annotations

from src.harness.context import HarnessContext
from src.models.harness import GateName, GateResult

_STRONG_ASSERTION_PATTERNS = (
    "が決定した",
    "が義務化される",
    "を義務付ける",
    "が施行された",
    "が正式決定",
    "が確定した",
    "は必須となる",
    "が義務となる",
    "全国一律で実施される",
)
_EARLY_STAGE_KEYWORDS = (
    "検討中", "審議中", "素案", "中間まとめ", "たたき台", "検討会議", "作業部会",
)
_LATE_STAGE_KEYWORDS = ("答申", "告示", "施行", "公布", "決定")


async def check(context: HarnessContext) -> GateResult:
    source_text = "\n".join(s.text for s in context.sources)
    draft_text = "\n".join(
        [
            context.draft.key_points.fact,
            context.draft.key_points.implication,
            context.draft.key_points.discussion,
            context.body_text,
        ]
    )

    found = [p for p in _STRONG_ASSERTION_PATTERNS if p in draft_text]
    if not found:
        return GateResult(gate=GateName.G4_ASSERTION_RISK, passed=True)

    is_early_stage = any(k in source_text for k in _EARLY_STAGE_KEYWORDS)
    is_late_stage = any(k in source_text for k in _LATE_STAGE_KEYWORDS)
    if is_early_stage and not is_late_stage:
        reason = (
            f"原文は検討中/中間段階を示す語のみだが、生成文に断定表現{found}が含まれています"
            "（政策段階の誤読の可能性）"
        )
        return GateResult(gate=GateName.G4_ASSERTION_RISK, passed=False, reason=reason)

    return GateResult(gate=GateName.G4_ASSERTION_RISK, passed=True)
