"""プロンプト層。一次情報とコンテキスト層の入力から、Gemini向けプロンプト文字列を組み立てる。

コンテキスト（学習指導要領・過去答申・自治体方針・教員フィードバック）はハードコードせず
ContextBundle経由で動的に注入する（CLAUDE.md 第2章）。
"""

from __future__ import annotations

from src.models.primary_source import RawDocument
from src.processors.context import ContextBundle


def _voice_instructions(context: ContextBundle) -> str:
    voice = context.editorial_voice
    banned = "、".join(voice.banned_phrases)
    return (
        f"## 文体・立場\n{voice.persona}\n\n"
        f"## 禁止表現（絶対に使わないこと）\n{banned}\n\n"
        f"## 数字の扱い\n{voice.number_rule}\n\n"
        f"## 立場表明の制約\n{voice.stance_rule}\n"
    )


def _context_injection(context: ContextBundle) -> str:
    def _section(title: str, items: list[str]) -> str:
        if not items:
            return f"## {title}\n(現時点では参照データなし)\n"
        joined = "\n".join(f"- {i}" for i in items)
        return f"## {title}\n{joined}\n"

    return "\n".join(
        [
            _section("関連する学習指導要領", context.curriculum_guidelines),
            _section("過去の関連答申", context.past_answers),
            _section("関連する自治体方針", context.local_policies),
            _section("教員からのフィードバック", context.teacher_feedback),
        ]
    )


def _self_repair_injection(prior_failures: list[str] | None) -> str:
    """自己修復ループ（最大3回リトライ）で、前回失敗したゲートの理由をプロンプトに再注入する
    （docs/ARCHITECTURE.md 2.3節）。"""
    if not prior_failures:
        return ""
    joined = "\n".join(f"- {reason}" for reason in prior_failures)
    return (
        "## 前回の生成で指摘された問題点（今回は必ず解消すること）\n"
        f"{joined}\n\n"
    )


def build_extraction_prompt(
    raw_document: RawDocument,
    context: ContextBundle,
    *,
    prior_failures: list[str] | None = None,
) -> str:
    """Fact/Implication/Discussion抽出＋ネタ選定スコアリングのプロンプトを組み立てる。"""
    return (
        "あなたは教育現場向けに一次情報を翻訳するアシスタントです。以下の一次情報から、"
        "現場教員が明日の校務で使える形でFact/Implication/Discussionを抽出し、"
        "記事化の優先度スコアを付けてください。\n\n"
        f"{_voice_instructions(context)}\n"
        f"{_context_injection(context)}\n"
        f"{_self_repair_injection(prior_failures)}"
        "## 一次情報\n"
        f"タイトル: {raw_document.title}\n"
        f"出典URL: {raw_document.url}\n"
        f"本文:\n{raw_document.raw_text}\n\n"
        "## 出力ルール\n"
        "- fact: 原文に明記された事実・数値のみを書く。原文にない数値の丸め・概算は禁止。\n"
        "- implication: 現場への含意。これがAIによる解釈であることが伝わる書き方にする。\n"
        "- discussion: まだ決まっていないこと・論点。\n"
        "- score_impact/score_timeliness/score_controversy: それぞれ1〜5の整数で評価する。\n"
    )


def build_x_thread_prompt(extraction: object, context: ContextBundle) -> str:
    return (
        "以下の内容をもとに、Xスレッド（140字以内の投稿を3〜5連）を作成してください。\n\n"
        f"{_voice_instructions(context)}\n"
        f"内容:\n{extraction}\n"
    )


def build_youtube_script_prompt(extraction: object, context: ContextBundle) -> str:
    return (
        "以下の内容をもとに、YouTube台本（NotebookLM等での音声化を想定し、漢字の読み仮名や"
        "句読点位置に配慮した読み上げやすい文体）と概要欄テキストを作成してください。\n\n"
        f"{_voice_instructions(context)}\n"
        f"内容:\n{extraction}\n"
    )
