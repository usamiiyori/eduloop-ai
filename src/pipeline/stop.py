"""`make stop`: キルスイッチ。system_control.paused を true にし、次回以降のL1/L2/L3
GitHub Actions実行を（開始直後に自己判定させて）即座にスキップさせる。

再開方法はあえて make コマンド化していない（CLAUDE.md第0章ルール4は日常操作を5〜6個の
コマンドに収めることが目的であり、緊急停止からの復帰は日常操作ではないため）。
docs/運用マニュアル.md にSQLでの再開手順を記載する。
"""

from __future__ import annotations

import asyncio
import sys

from src.config import get_settings
from src.store import system_control


async def run() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が.envに未設定のため停止できません。")
        return

    await system_control.set_paused(True, reason="make stop によるオーナーの手動停止")
    print("停止しました。次回以降のL1(収集)/L2(承認連携)/L3(月次)は自動的にスキップされます。")
    print("再開する場合は docs/運用マニュアル.md の「キルスイッチの解除方法」を参照してください。")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run())


if __name__ == "__main__":
    main()
