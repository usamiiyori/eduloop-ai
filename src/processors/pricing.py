"""Gemini APIの料金換算。docs/運用マニュアル.md に記載の通り、確認済みなのは
gemini-2.5-flash の有料プラン料金のみ（https://ai.google.dev/gemini-api/docs/pricing 、
2026-08-19確認）。未確認のモデルは推測で単価を作らず、コスト0円・not_confirmedとして扱う
（CLAUDE.md第5章「推測でコードを書かない」）。

無料枠を使っている場合の実際の請求額は0円だが、本モジュールは常に「有料プラン料金で計算した
上限見積り」を返す（実際の請求額とは異なりうる旨は docs/運用マニュアル.md に明記）。
"""

from __future__ import annotations

from dataclasses import dataclass

# (入力 USD/1Mトークン, 出力 USD/1Mトークン)
_CONFIRMED_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
}


@dataclass
class CostEstimate:
    usd: float
    confirmed: bool


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> CostEstimate:
    pricing = _CONFIRMED_PRICING_USD_PER_1M.get(model)
    if pricing is None:
        return CostEstimate(usd=0.0, confirmed=False)
    input_rate, output_rate = pricing
    usd = (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
    return CostEstimate(usd=usd, confirmed=True)
