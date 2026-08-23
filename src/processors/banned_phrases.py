"""生成後の禁止語（AI的定型句）機械チェック（CLAUDE.md 第5章）。"""

from __future__ import annotations

from src.models.editorial import EditorialVoiceConfig


def find_banned_phrases(text: str, voice: EditorialVoiceConfig) -> list[str]:
    return [phrase for phrase in voice.banned_phrases if phrase in text]
