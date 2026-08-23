"""note向け下書き整形。note公開APIは存在しない前提のため、コピペ用のMarkdown文字列を生成する
（docs/ARCHITECTURE.md 第8章）。
"""

from __future__ import annotations


def format_for_note(title: str, body_markdown: str) -> str:
    """noteエディタへのコピペを想定し、見出し前に区切り線を挿入して整形する。"""
    sectioned = body_markdown.replace("## ", "\n---\n\n## ")
    return f"# {title}\n{sectioned.strip()}\n"
