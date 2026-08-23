"""通知はSlackではなくメール（Gmail SMTP）で行う（2026-08-23、オーナーの判断でSlackから移行）。

差出人(SMTP_USER)は SCRAPER_CONTACT_URL と同じ「通知専用アカウント」を使う想定。
オーナー本人のメールアドレス(NOTIFY_TO_EMAIL)は宛先としてのみ使い、外部には一切公開しない
（収集先サイトへのUser-Agent等には出さない。CLAUDE.md 第9章参照）。

Gmail SMTP はアプリパスワード認証を使う（2段階認証を有効化したアカウントで
https://myaccount.google.com/apppasswords から発行。2026-08-23確認、
docs/運用マニュアル.md 参照）。
"""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = structlog.get_logger(__name__)


class MissingSmtpConfigError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "SMTP_USER / SMTP_APP_PASSWORD / NOTIFY_TO_EMAIL のいずれかが.envに"
            "設定されていません。docs/運用マニュアル.md の「通知メールの設定方法」を"
            "参照してください。"
        )


async def send_email(subject: str, body_text: str) -> None:
    """設定未完了の場合は例外を出さず警告ログのみ（他の処理を止めないため）。"""
    settings = get_settings()
    if not (settings.smtp_user and settings.smtp_app_password and settings.notify_to_email):
        logger.warning("email_notify_not_configured", subject=subject)
        return

    await asyncio.to_thread(_send_sync, subject, body_text)


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _send_sync(subject: str, body_text: str) -> None:
    settings = get_settings()
    message = MIMEText(body_text, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.smtp_user
    message["To"] = settings.notify_to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_app_password)
        server.sendmail(settings.smtp_user, [settings.notify_to_email], message.as_string())
