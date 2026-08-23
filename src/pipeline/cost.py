"""`make cost`: LLM APIの当月推定コストを日本語で表示する。"""

from __future__ import annotations

import asyncio
import sys

from src.config import get_settings
from src.store import cost_log


async def run() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が.envに未設定のため確認できません。")
        print("docs/運用マニュアル.md の「Supabaseプロジェクトの作成方法」を参照してください。")
        return

    today = await cost_log.today_total_usd()
    month = await cost_log.month_total_usd()
    limit = settings.llm_daily_cost_limit_usd

    print("=== EduLoop AI 推定コスト ===")
    print(f"本日: ${today:.4f}（日次上限: ${limit:.2f}）")
    print(f"今月合計: ${month:.4f}")
    print()
    print(
        "※ この金額はGemini有料プラン料金で計算した「上限見積り」です。"
        "無料枠を使っている場合、実際の請求額は0円のことがあります。"
        "料金体系の最新情報は https://ai.google.dev/gemini-api/docs/pricing を確認してください。"
    )
    if today >= limit:
        print(
            "\n⚠ 本日のコストが上限に達しています。"
            "L1の自動収集は次の日次リセットまでスキップされます。"
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run())


if __name__ == "__main__":
    main()
