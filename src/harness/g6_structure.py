"""G6 構造ゲート。

draft.format に応じたPydantic v2モデル（WebArticle/XThread/YouTubeScript）に
context.structure_raw を model_validate し、スキーマ違反（4部構成欠落・140字超過・
order_index不整合等）を検出する。実際のバリデーションルールは src/models/draft.py 側に
定義済みであり、本ゲートはその実行と結果の GateResult 変換のみを担う。
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from src.harness.context import HarnessContext
from src.models.draft import DraftFormat, WebArticle, XThread, YouTubeScript
from src.models.harness import GateName, GateResult

_FORMAT_MODELS: dict[DraftFormat, type[BaseModel]] = {
    DraftFormat.WEB_ARTICLE: WebArticle,
    DraftFormat.X_THREAD: XThread,
    DraftFormat.YOUTUBE_SCRIPT: YouTubeScript,
}


async def check(context: HarnessContext) -> GateResult:
    model_cls = _FORMAT_MODELS[context.draft.format]
    try:
        model_cls.model_validate(context.structure_raw)
    except ValidationError as exc:
        reasons = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return GateResult(gate=GateName.G6_STRUCTURE, passed=False, reason=reasons)
    return GateResult(gate=GateName.G6_STRUCTURE, passed=True)
