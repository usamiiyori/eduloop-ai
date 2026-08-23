"""X（旧Twitter）投稿モジュール。draft(下書き→手動投稿)とapi(自動投稿)を切り替え可能にする
（docs/ARCHITECTURE.md 第8章）。

X API v2 は2026年2月以降、新規開発者向けの無料枠が廃止され、投稿作成 $0.015/件
（リンクを含む場合$0.20/件）の従量課金制になっている（https://docs.x.com/x-api/ 系の複数の
料金解説記事で2026-08-22確認。詳細は docs/運用マニュアル.md 参照）。api モードは
X_API_KEY 等が確認・設定された後にPhase6で実装する。draft モードのみ現時点で提供する。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import get_settings


@dataclass
class XPublishResult:
    mode: str
    formatted_text: str
    posted: bool


def format_thread_for_manual_posting(posts: list[str]) -> str:
    return "\n\n".join(f"{i + 1}/{len(posts)}\n{text}" for i, text in enumerate(posts))


async def publish_x_thread(posts: list[str]) -> XPublishResult:
    mode = get_settings().x_publish_mode
    formatted = format_thread_for_manual_posting(posts)

    if mode == "draft":
        return XPublishResult(mode=mode, formatted_text=formatted, posted=False)

    if mode == "api":
        raise NotImplementedError(
            "X_PUBLISH_MODE=api は未実装です。X APIは2026年時点で従量課金制"
            "（投稿$0.015/件、リンク付き$0.20/件）のため、実装前にオーナーの課金設定・"
            "APIキー確認が必要です（docs/運用マニュアル.md参照）。それまではdraftモードを"
            "使用してください。"
        )

    raise ValueError(f"未知のX_PUBLISH_MODEです: {mode!r}（draft または api を指定）")
