"""スクレイパー共通のHTTPユーティリティ。User-Agent明記・robots.txt遵守・レート制限・リトライを一箇所に集約する。"""

from __future__ import annotations

import hashlib

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.models.source import SourceConfig
from src.scrapers import rate_limit
from src.scrapers.robots import is_allowed

logger = structlog.get_logger(__name__)

APP_NAME = "EduLoopAI-Collector/0.1"


class RobotsDisallowedError(RuntimeError):
    """robots.txt が明示的にアクセスを禁止している場合に送出する。"""


def build_user_agent() -> str:
    contact = get_settings().scraper_contact_url
    if not contact:
        logger.warning("scraper_contact_url_unset")
        contact = "contact-not-configured"
    return f"{APP_NAME} (+{contact})"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def fetch_bytes(client: httpx.AsyncClient, source: SourceConfig) -> bytes:
    """robots.txt確認・レート制限・指数バックオフ付きリトライを経てURLを取得する。"""
    if not await is_allowed(client, source, build_user_agent()):
        raise RobotsDisallowedError(f"robots.txtにより収集を禁止されています: {source.url}")
    await rate_limit.wait_for_turn(source.id, source.crawl_interval_seconds)
    response = await client.get(source.url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.content
