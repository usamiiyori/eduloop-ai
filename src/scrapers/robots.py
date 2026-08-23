"""robots.txt 遵守チェック。SourceConfig.robots_txt_override が立っている場合のみ例外を許可する。"""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

from src.models.source import SourceConfig

logger = structlog.get_logger(__name__)

_cache: dict[str, RobotFileParser] = {}


async def _fetch_robots(client: httpx.AsyncClient, origin: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(f"{origin}/robots.txt")
    try:
        response = await client.get(f"{origin}/robots.txt", timeout=10)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            # robots.txtが存在しない場合は「制限なし」として扱う（一般的な解釈）。
            parser.parse([])
    except httpx.HTTPError as exc:
        logger.warning("robots_txt_fetch_failed", origin=origin, error=str(exc))
        parser.parse([])
    return parser


async def is_allowed(client: httpx.AsyncClient, source: SourceConfig, user_agent: str) -> bool:
    """robots.txt がこのURLへのアクセスを許可しているか判定する。

    source.robots_txt_override=true の場合はチェックをスキップして許可する
    （config/sources.yaml の override_justification で根拠を必須化している）。
    """
    if source.robots_txt_override:
        logger.info(
            "robots_txt_override_applied",
            source_id=source.id,
            justification=source.override_justification,
        )
        return True

    origin = f"{urlparse(source.url).scheme}://{urlparse(source.url).netloc}"
    if origin not in _cache:
        _cache[origin] = await _fetch_robots(client, origin)
    allowed = _cache[origin].can_fetch(user_agent, source.url)
    if not allowed:
        logger.warning("robots_txt_disallowed", source_id=source.id, url=source.url)
    return allowed
