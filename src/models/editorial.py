"""編集ペルソナ・文体規定（config/editorial_voice.yaml）に対応する Pydantic v2 モデル。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EditorialVoiceConfig(BaseModel):
    """オーナーがコードを触らず調整できる編集ペルソナ設定（CLAUDE.md 第5章）。"""

    persona: str = Field(description="一人称・立場の説明。プロンプトにそのまま埋め込む")
    banned_phrases: list[str] = Field(description="AI的定型句の禁止語リスト。生成後に機械チェック")
    required_sections: list[str] = Field(description="Web記事の必須4部構成の見出し")
    number_rule: str = Field(description="数字の扱いに関する規定")
    stance_rule: str = Field(description="政策への賛否表明に関する規定")


def load_editorial_voice(path: str | Path = "config/editorial_voice.yaml") -> EditorialVoiceConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return EditorialVoiceConfig.model_validate(raw)
