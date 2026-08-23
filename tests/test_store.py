"""Phase6: Supabase永続化層(src/store)のテスト。実Supabaseへは接続せずrespxでモックする。"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from src.store import supabase_client as sb
from src.store.supabase_client import SupabaseNotConfiguredError, SupabaseRequestError

FAKE_URL = "https://fake.supabase.co"


def _patched_settings():
    return patch(
        "src.store.supabase_client.get_settings",
        return_value=type(
            "S", (), {"supabase_url": FAKE_URL, "supabase_service_role_key": "fake-key"}
        )(),
    )


class TestSupabaseClient:
    async def test_raises_japanese_error_when_not_configured(self) -> None:
        with patch(
            "src.store.supabase_client.get_settings",
            return_value=type("S", (), {"supabase_url": "", "supabase_service_role_key": ""})(),
        ):
            with pytest.raises(SupabaseNotConfiguredError, match="SUPABASE_URL"):
                await sb.select("drafts")

    async def test_select_returns_json_body(self) -> None:
        async with respx.mock:
            respx.get(f"{FAKE_URL}/rest/v1/drafts").mock(
                return_value=httpx.Response(200, json=[{"id": "1"}])
            )
            with _patched_settings():
                rows = await sb.select("drafts")
        assert rows == [{"id": "1"}]

    async def test_insert_sends_prefer_representation_header(self) -> None:
        async with respx.mock:
            route = respx.post(f"{FAKE_URL}/rest/v1/drafts").mock(
                return_value=httpx.Response(201, json=[{"id": "1"}])
            )
            with _patched_settings():
                rows = await sb.insert("drafts", {"status": "draft"})
        assert rows == [{"id": "1"}]
        assert route.calls.last.request.headers["Prefer"] == "return=representation"

    async def test_update_sends_match_as_eq_filter(self) -> None:
        async with respx.mock:
            route = respx.patch(f"{FAKE_URL}/rest/v1/drafts").mock(
                return_value=httpx.Response(200, json=[{"id": "1", "status": "approved"}])
            )
            with _patched_settings():
                await sb.update("drafts", match={"id": "1"}, values={"status": "approved"})
        assert route.calls.last.request.url.params["id"] == "eq.1"

    async def test_error_status_raises_supabase_request_error(self) -> None:
        async with respx.mock:
            respx.get(f"{FAKE_URL}/rest/v1/drafts").mock(
                return_value=httpx.Response(404, text="not found")
            )
            with _patched_settings():
                with pytest.raises(SupabaseRequestError):
                    await sb.select("drafts")
