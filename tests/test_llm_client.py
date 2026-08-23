"""llm_client のテスト。実際のGemini APIへは接続せず、google.genai.Clientをモックする。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.processors.llm_client import MissingApiKeyError, generate_structured, get_client


class _Answer(BaseModel):
    value: str


def test_missing_api_key_raises_japanese_error() -> None:
    with patch("src.processors.llm_client.get_settings") as mock_settings:
        mock_settings.return_value.google_genai_api_key = ""
        with pytest.raises(MissingApiKeyError, match="GOOGLE_GENAI_API_KEY"):
            get_client()


async def test_generate_structured_returns_parsed_response() -> None:
    fake_response = MagicMock()
    fake_response.parsed = _Answer(value="ok")

    fake_client = MagicMock()
    fake_client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    with patch("src.processors.llm_client.get_client", return_value=fake_client):
        result = await generate_structured("prompt", _Answer, model="gemini-test")

    assert result == _Answer(value="ok")
    fake_client.aio.models.generate_content.assert_awaited_once()
    _, kwargs = fake_client.aio.models.generate_content.call_args
    assert kwargs["model"] == "gemini-test"
    assert kwargs["contents"] == "prompt"


async def test_generate_structured_raises_on_unparsable_response() -> None:
    fake_response = MagicMock()
    fake_response.parsed = None
    fake_response.text = "not json"

    fake_client = MagicMock()
    fake_client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    with patch("src.processors.llm_client.get_client", return_value=fake_client):
        with pytest.raises(ValueError, match="パース"):
            await generate_structured("prompt", _Answer)
