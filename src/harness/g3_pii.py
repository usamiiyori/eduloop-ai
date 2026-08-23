"""G3 個人情報(PII)ゲート。

正規表現によるメール/電話番号検出と、呼び出し側が渡す固有名詞ブロックリスト（生徒名・教員個人名・
特定可能な学校名等）の一致検査を行う（第一段）。検出時は自動マスクせずブロックして人間に回す
（CLAUDE.md 第2章）。モデレーションAPIによる第二段検査は、外部API接続が確定してから追加する
（Phase4/6。日本語人名の一般検出は正規表現だけでは実用的な精度が出ないため）。
"""

from __future__ import annotations

import re

from src.harness.context import HarnessContext
from src.models.harness import GateName, GateResult

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"0\d{1,4}-\d{1,4}-\d{3,4}")


def _mask(value: str) -> str:
    # \w はUnicode対応のためメールのローカル部の前に日本語文字が誤って含まれることはないが、
    # 念のため先頭3文字のみ表示しPII全体はログに残さない。
    return f"{value[:3]}***" if len(value) > 3 else "***"


async def check(context: HarnessContext) -> GateResult:
    text = "\n".join(
        [
            context.draft.key_points.fact,
            context.draft.key_points.implication,
            context.draft.key_points.discussion,
            context.body_text,
        ]
    )
    failures: list[str] = []

    for match in _EMAIL_RE.finditer(text):
        failures.append(f"メールアドレスと思われる文字列を検出: {_mask(match.group())}")
    for match in _PHONE_RE.finditer(text):
        failures.append(f"電話番号と思われる文字列を検出: {_mask(match.group())}")
    for name in context.pii_blocklist:
        if name and name in text:
            failures.append(f"個人・学校を特定しうる語「{name}」を検出しました")

    if failures:
        return GateResult(gate=GateName.G3_PII, passed=False, reason="; ".join(failures))
    return GateResult(gate=GateName.G3_PII, passed=True)
