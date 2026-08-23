"""google-genai (Gemini) クライアントの薄いラッパー。

API仕様は https://googleapis.github.io/python-genai/ (2026-08-18確認) に基づく:
  client.aio.models.generate_content(model=..., contents=..., config=GenerateContentConfig(
      response_mime_type="application/json", response_schema=<Pydantic model>))
戻り値の response.parsed に Pydantic モデルのインスタンスが入る。
"""

from __future__ import annotations

from typing import TypeVar

import structlog
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = structlog.get_logger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class MissingApiKeyError(RuntimeError):
    """GOOGLE_GENAI_API_KEY が未設定の場合に送出する。日本語メッセージで理由と対処法を示す。"""

    def __init__(self) -> None:
        super().__init__(
            "GOOGLE_GENAI_API_KEYが設定されていません。"
            ".env に Google AI Studio (https://aistudio.google.com/) で発行したAPIキーを"
            "設定してください（docs/運用マニュアル.md 参照）。"
        )


def get_client() -> genai.Client:
    api_key = get_settings().google_genai_api_key
    if not api_key:
        raise MissingApiKeyError
    return genai.Client(api_key=api_key)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(APIError),
)
async def generate_structured(
    prompt: str, response_schema: type[SchemaT], *, model: str | None = None
) -> SchemaT:
    """プロンプトを送りPydanticスキーマに沿った構造化出力を取得する。"""
    client = get_client()
    resolved_model = model or get_settings().google_genai_model
    response = await client.aio.models.generate_content(
        model=resolved_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    parsed = response.parsed
    if not isinstance(parsed, response_schema):
        logger.error("llm_response_parse_failed", model=resolved_model, raw_text=response.text)
        raise ValueError("LLM応答を期待したスキーマにパースできませんでした")
    return parsed
