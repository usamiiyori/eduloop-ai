"""G5 重複・既報ゲート。

過去の生成物本文とのテキスト類似度を比較し、実質同一の再投稿を検出する。Phase3時点では
埋め込みコサイン類似度の代わりに difflib による文字列類似度を暫定指標として使う（GOOGLE_GENAI_
API_KEY設定後、Phase4/6で埋め込みベースに置き換える）。閾値超過は「続報」フォーマットへの
切替を促す。
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.harness.context import HarnessContext
from src.models.harness import GateName, GateResult

_SIMILARITY_THRESHOLD = 0.8


async def check(context: HarnessContext) -> GateResult:
    for index, past_text in enumerate(context.past_draft_texts):
        ratio = SequenceMatcher(None, context.body_text, past_text, autojunk=False).ratio()
        if ratio >= _SIMILARITY_THRESHOLD:
            reason = (
                f"過去記事#{index}と類似度{ratio:.1%}。実質同一の可能性があるため"
                "「続報」フォーマットへの切替を検討してください"
            )
            return GateResult(gate=GateName.G5_DUPLICATE, passed=False, reason=reason)
    return GateResult(gate=GateName.G5_DUPLICATE, passed=True)
