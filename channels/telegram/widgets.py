"""Telegram-specific rendering for Widget types.

Phase 1 mapping:
    - text → plain HTML message
    - file → sendDocument
    - quiz_url / flashcard_url → message with an inline keyboard button
"""

from __future__ import annotations

from channels._base import Widget
from channels.telegram.formatting import markdown_to_html


def render_widget(widget: Widget) -> dict:
    """Turn a Widget into kwargs for the telegram Bot send_* methods.

    Returns a dict with:
        - method: "send_message" | "send_document"
        - payload: kwargs to splat into the PTB call
    """
    if widget.type == "text":
        return {
            "method": "send_message",
            "payload": {
                "text": markdown_to_html(widget.content),
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
        }
    if widget.type == "file":
        return {
            "method": "send_document",
            "payload": {"document": widget.content},
        }
    if widget.type in {"quiz_url", "flashcard_url"}:
        label = "Open quiz" if widget.type == "quiz_url" else "Open flashcards"
        return {
            "method": "send_message",
            "payload": {
                "text": f"{label}: {widget.content}",
                "disable_web_page_preview": True,
            },
        }
    raise ValueError(f"unsupported widget type: {widget.type}")
