"""Supabase PostgREST への薄い非同期HTTPラッパー。

service_role キーでのみ接続する。RLSはservice_roleを常にバイパスする仕様のため、
sql/0001_initial_schema.sql 冒頭のコメントの通り「万一の誤用に対する防御」として機能する
（実際のアクセス制御はここ、つまりstoreパッケージの外に生のservice_roleキーを流出させない
運用で担保する）。
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import get_settings


class SupabaseNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が .env に設定されていません。"
            "docs/運用マニュアル.md の「Supabaseプロジェクトの作成方法」を参照してください。"
        )


class SupabaseRequestError(RuntimeError):
    def __init__(self, method: str, path: str, response: httpx.Response) -> None:
        super().__init__(
            f"Supabaseへのリクエストに失敗しました ({method} {path}): "
            f"status={response.status_code} body={response.text[:500]}"
        )
        self.status_code = response.status_code


def _base_url_and_headers() -> tuple[str, dict[str, str]]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseNotConfiguredError
    key = settings.supabase_service_role_key
    return settings.supabase_url.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
)
async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json: Any | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    base_url, headers = _base_url_and_headers()
    if extra_headers:
        headers = {**headers, **extra_headers}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method, f"{base_url}{path}", params=params, json=json, headers=headers
        )
    if response.status_code >= 400:
        raise SupabaseRequestError(method, path, response)
    return response


async def select(table: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    response = await _request("GET", f"/rest/v1/{table}", params=params)
    body: list[dict[str, Any]] = response.json()
    return body


async def insert(
    table: str, rows: dict[str, Any] | list[dict[str, Any]], *, on_conflict: str | None = None
) -> list[dict[str, Any]]:
    """1件またはcomplex件を挿入する。on_conflict指定時はupsert（重複時は上書き）になる。"""
    params = {"on_conflict": on_conflict} if on_conflict else None
    prefer = "return=representation"
    if on_conflict:
        prefer += ",resolution=merge-duplicates"
    response = await _request(
        "POST", f"/rest/v1/{table}", params=params, json=rows, extra_headers={"Prefer": prefer}
    )
    body: list[dict[str, Any]] = response.json()
    return body


async def update(
    table: str, *, match: dict[str, str], values: dict[str, Any]
) -> list[dict[str, Any]]:
    params = {k: f"eq.{v}" for k, v in match.items()}
    response = await _request(
        "PATCH",
        f"/rest/v1/{table}",
        params=params,
        json=values,
        extra_headers={"Prefer": "return=representation"},
    )
    body: list[dict[str, Any]] = response.json()
    return body


async def rpc(fn: str, args: dict[str, Any]) -> Any:
    response = await _request("POST", f"/rest/v1/rpc/{fn}", json=args)
    return response.json()
