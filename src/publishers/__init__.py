"""L2承認後のみ呼び出される配信モジュール（Web/X/note等）。承認フラグ未確認での実行を禁止する。
review_request のみ例外で、承認"依頼"通知（L1→L2の橋渡し）のため承認前に呼び出す。"""

from __future__ import annotations

from src.publishers.note_formatter import format_for_note
from src.publishers.revenue_funnel import append_revenue_funnel
from src.publishers.review_request import notify_review_needed
from src.publishers.utm import build_utm_url
from src.publishers.web_publish import NotApprovedError, publish_web_article
from src.publishers.x_publisher import XPublishResult, publish_x_thread

__all__ = [
    "NotApprovedError",
    "XPublishResult",
    "append_revenue_funnel",
    "build_utm_url",
    "format_for_note",
    "notify_review_needed",
    "publish_web_article",
    "publish_x_thread",
]
