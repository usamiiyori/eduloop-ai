"""L2承認依頼通知（Slack）。生成物がharness(G1〜G6)を通過した直後、承認前の人間に
「レビューしてください」と知らせる。Slack Incoming Webhookは送信専用のため、実際の
承認/却下操作は別途Web承認画面（Supabase接続後に実装）で行う（CLAUDE.md 第9章）。

Slack Incoming Webhookのペイロード形式は https://docs.slack.dev/messaging/
sending-messages-using-incoming-webhooks (2026-08-22確認) に基づく。
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.models.draft import Draft


class MissingWebhookError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "SLACK_WEBHOOK_URLが設定されていません。.env に Slack Incoming Webhook の"
            "URLを設定してください（docs/運用マニュアル.md 参照）。"
        )


def build_slack_payload(draft: Draft, title: str, review_url: str) -> dict[str, object]:
    return {
        "text": f"レビュー依頼: {title}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*レビュー依頼: {title}*\n"
                        f"スコア: {draft.score_total}"
                        f"（インパクト{draft.score_impact}×速報性{draft.score_timeliness}"
                        f"×論点{draft.score_controversy}）\n"
                        f"フォーマット: {draft.format.value}\n"
                        f"<{review_url}|承認・却下・修正指示はこちら>"
                    ),
                },
            }
        ],
    }


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def notify_review_needed(draft: Draft, title: str, review_url: str) -> None:
    webhook_url = get_settings().slack_webhook_url
    if not webhook_url:
        raise MissingWebhookError

    payload = build_slack_payload(draft, title, review_url)
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
