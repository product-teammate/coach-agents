"""Markdown → Telegram-safe HTML conversion.

Telegram's Markdown parser is strict; we favor HTML output which is more
forgiving. This module does just enough: escape HTML special characters,
then translate a small subset of Markdown (bold, italic, inline code,
code fence, links).
"""

from __future__ import annotations

import html
import re


_CODE_FENCE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def markdown_to_html(text: str) -> str:
    """Convert a small, safe Markdown subset to Telegram HTML."""
    # Protect code fences first.
    placeholders: list[str] = []

    def _stash_fence(match: re.Match[str]) -> str:
        placeholders.append(match.group(2))
        return f"\0FENCE{len(placeholders) - 1}\0"

    stashed = _CODE_FENCE.sub(_stash_fence, text)
    escaped = html.escape(stashed, quote=False)

    escaped = _INLINE_CODE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD.sub(r"<b>\1</b>", escaped)
    escaped = _ITALIC.sub(r"<i>\1</i>", escaped)
    escaped = _LINK.sub(r'<a href="\2">\1</a>', escaped)

    for idx, body in enumerate(placeholders):
        escaped = escaped.replace(
            f"\0FENCE{idx}\0", f"<pre>{html.escape(body, quote=False)}</pre>"
        )
    return escaped
