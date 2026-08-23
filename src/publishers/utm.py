"""外部リンクへのUTM自動付与ユーティリティ（docs/ARCHITECTURE.md 第4章の必須実装）。"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def build_utm_url(
    base_url: str,
    *,
    source: str,
    medium: str,
    campaign: str,
    content: str | None = None,
) -> str:
    """base_url の既存クエリを保持したまま utm_* パラメータを付与する。"""
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query))
    query.update(
        {
            "utm_source": source,
            "utm_medium": medium,
            "utm_campaign": campaign,
        }
    )
    if content:
        query["utm_content"] = content
    return urlunparse(parsed._replace(query=urlencode(query)))
