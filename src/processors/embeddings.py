"""Gemini埋め込みAPIの薄いラッパー。G1(事実整合性)・G5(重複判定)の意味的類似度判定で使う。

API仕様は https://googleapis.github.io/python-genai/ (2026-08-22、実APIレスポンスで確認)に基づく:
  client.aio.models.embed_content(model="gemini-embedding-001", contents=[...])
  -> response.embeddings: list[ContentEmbedding]、各要素の .values が float配列(3072次元)。
"""

from __future__ import annotations

import math

from google.genai.errors import APIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.processors.llm_client import get_client

EMBEDDING_MODEL = "gemini-embedding-001"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(APIError),
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_client()
    # list[str] は実行時には問題なく受け付けられるが、SDKの型スタブがlist型の不変性により
    # list[str | Image | ...] 等のUnionと厳密一致しないためmypyが誤検知する（実挙動は確認済み）。
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL, contents=list(texts)  # type: ignore[arg-type]
    )
    if response.embeddings is None:
        raise ValueError("Gemini埋め込みAPIから空の応答が返されました")
    return [list(e.values or []) for e in response.embeddings]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
