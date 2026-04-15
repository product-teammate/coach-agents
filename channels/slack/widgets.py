"""Slack-specific rendering for Widget types.

Phase 1 mapping:
    - text          -> chat.postMessage with mrkdwn text
    - file          -> files_upload_v2
    - quiz_url      -> chat.postMessage with intro + URL (unfurl enabled)
    - flashcard_url -> chat.postMessage with intro + URL (unfurl enabled)
"""

from __future__ import annotations

from dataclasses import dataclass

from channels._base import Widget
from channels.slack.formatting import markdown_to_mrkdwn


@dataclass(frozen=True)
class RenderedWidget:
    """Result of rendering a Widget for Slack.

    ``method`` is one of ``post_message`` | ``upload_file``. ``payload`` is
    the kwargs dict to splat into the matching ``AsyncWebClient`` call. For
    ``upload_file`` the ``file`` key holds a local filesystem path.
    """

    method: str
    payload: dict


def render_widget(widget: Widget) -> RenderedWidget:
    """Turn a Widget into a RenderedWidget for the Slack adapter to send."""
    if widget.type == "text":
        return RenderedWidget(
            method="post_message",
            payload={
                "text": markdown_to_mrkdwn(widget.content),
            },
        )
    if widget.type == "file":
        return RenderedWidget(
            method="upload_file",
            payload={"file": widget.content},
        )
    if widget.type == "quiz_url":
        return RenderedWidget(
            method="post_message",
            payload={
                "text": f":memo: Quiz ready: {widget.content}",
                "unfurl_links": True,
            },
        )
    if widget.type == "flashcard_url":
        return RenderedWidget(
            method="post_message",
            payload={
                "text": f":card_index: Flashcards ready: {widget.content}",
                "unfurl_links": True,
            },
        )
    raise ValueError(f"unsupported widget type: {widget.type}")
