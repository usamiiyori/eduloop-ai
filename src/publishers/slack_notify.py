"""汎用Slack通知（レビュー依頼以外）。コスト超過・ソース疎通異常・L2配信完了・L3月次レポート等、
review_request.py（レビュー依頼専用フォーマット）でカバーしない通知に使う。
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings


async def send_text(text: str) -> None:
    """SLACK_WEBHOOK_URL未設定の場合は何もしない（Phase5以前の環境でも他処理を壊さないため）。"""
    webhook_url = get_settings().slack_webhook_url
    if not webhook_url:
        return
    await _post(webhook_url, text)


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def _post(webhook_url: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json={"text": text}, timeout=10)
        response.raise_for_status()
