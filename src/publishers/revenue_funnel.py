"""Web記事末尾へのnote有料版導線・問い合わせ導線の自動挿入（docs/ARCHITECTURE.md 第4章）。"""

from __future__ import annotations

from src.publishers.utm import build_utm_url


def append_revenue_funnel(
    body_markdown: str,
    *,
    slug: str,
    note_url: str | None,
    contact_url: str,
) -> str:
    """L2承認後、Web記事本文の末尾に収益・信用導線を追記する。

    note_url が未設定（まだnote有料版記事を用意していない）場合はnote導線を省略する。
    """
    lines = [body_markdown.rstrip(), "", "---", ""]
    if note_url:
        tagged_note_url = build_utm_url(
            note_url, source="eduloop_web", medium="article_footer", campaign=slug
        )
        lines.append(f"より詳しい実践編は note有料マガジンで解説しています → {tagged_note_url}")
        lines.append("")
    tagged_contact_url = build_utm_url(
        contact_url, source="eduloop_web", medium="article_footer", campaign=slug
    )
    lines.append(f"取材・登壇・研修のご相談はこちらから → {tagged_contact_url}")
    return "\n".join(lines)
