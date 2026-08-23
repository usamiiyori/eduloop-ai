"""プロンプト層・コンテキスト層。生データを Fact/Implication/Discussion/Citation へ変換する。"""

from __future__ import annotations

from src.processors.context import ContextBundle, build_default_context
from src.processors.generator import (
    generate_web_article,
    generate_x_thread,
    generate_youtube_script,
)
from src.processors.scoring import passes_threshold

__all__ = [
    "ContextBundle",
    "build_default_context",
    "generate_web_article",
    "generate_x_thread",
    "generate_youtube_script",
    "passes_threshold",
]
