"""L2承認後のみ呼び出される配信モジュール（Web/X/note等）。承認フラグ未確認での実行を禁止する。
email_notify のみ例外で、レビュー依頼・運用通知（承認前・承認後どちらでも使う）のため
承認フラグと無関係に呼び出してよい。"""

from __future__ import annotations

from src.publishers.email_notify import send_email
from src.publishers.note_formatter import format_for_note
from src.publishers.revenue_funnel import append_revenue_funnel
from src.publishers.utm import build_utm_url
from src.publishers.web_publish import NotApprovedError, publish_web_article
from src.publishers.x_publisher import XPublishResult, publish_x_thread

__all__ = [
    "NotApprovedError",
    "XPublishResult",
    "append_revenue_funnel",
    "build_utm_url",
    "format_for_note",
    "publish_web_article",
    "publish_x_thread",
    "send_email",
]
