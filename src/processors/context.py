"""コンテキスト層。学習指導要領・過去答申・自治体方針・編集ペルソナ・教員フィードバックを
動的注入するための束（ContextBundle）を組み立てる。

Supabase未接続のPhase4時点では curriculum_guidelines / past_answers / local_policies /
teacher_feedback は空リストがデフォルトになる（ハードコードではなく「まだ接続先がない」状態）。
Phase6でSupabase接続後、これらを埋めるローダーに差し替える。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.editorial import EditorialVoiceConfig, load_editorial_voice


@dataclass
class ContextBundle:
    editorial_voice: EditorialVoiceConfig
    curriculum_guidelines: list[str] = field(default_factory=list)
    past_answers: list[str] = field(default_factory=list)
    local_policies: list[str] = field(default_factory=list)
    teacher_feedback: list[str] = field(default_factory=list)


def build_default_context(
    editorial_voice_path: str = "config/editorial_voice.yaml",
) -> ContextBundle:
    """Supabase接続前の暫定コンテキスト。editorial_voiceのみ実データ、他は空。"""
    return ContextBundle(editorial_voice=load_editorial_voice(editorial_voice_path))
