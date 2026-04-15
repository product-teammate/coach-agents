"""Markdown -> Slack mrkdwn conversion.

Slack mrkdwn differs from standard Markdown:
    - Bold uses single ``*`` (not ``**``)
    - Italic uses single ``_`` (not ``*``)
    - Headers are not supported (convert to bold)
    - Links use ``<url|label>`` (not ``[label](url)``)
    - Fenced code blocks survive as triple backticks

This module handles the subset the coach actually emits. Code fences are
protected during conversion so their contents are left untouched.
"""

from __future__ import annotations

import re

_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`[^`]+`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_HEADER = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def markdown_to_mrkdwn(text: str) -> str:
    """Convert a small, safe Markdown subset to Slack mrkdwn.

    Code fences are preserved verbatim. Inline code is preserved as-is
    (backticks survive in mrkdwn). Headers become bold lines.
    """
    if not text:
        return ""

    stash: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        stash.append(match.group(0))
        return f"\x00S{len(stash) - 1}\x00"

    text = _CODE_FENCE.sub(_stash, text)
    text = _INLINE_CODE.sub(_stash, text)

    text = _HEADER.sub(r"*\1*", text)
    text = _BOLD.sub(r"*\1*", text)
    text = _MD_LINK.sub(r"<\2|\1>", text)
    # Convert leftover single-star italics to underscore italics.
    text = _ITALIC.sub(r"_\1_", text)

    for i, block in enumerate(stash):
        text = text.replace(f"\x00S{i}\x00", block)
    return text
