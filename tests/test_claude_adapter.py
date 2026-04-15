"""Unit tests for the Claude Code brain adapter stream parser.

The tests avoid spawning a real subprocess; instead they feed fake
stdout lines into ``_parse_stream`` and verify the yielded text.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import pytest

from brains.claude_code.adapter import (
    ClaudeCodeError,
    _parse_stream,
)


class _FakeStream:
    """Minimal asyncio.StreamReader stand-in that yields queued lines."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


def _line(obj: dict) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")


async def _collect(it: AsyncIterator[str]) -> list[str]:
    out: list[str] = []
    async for chunk in it:
        out.append(chunk)
    return out


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.unit
def test_assistant_only_event_yields_all_text_blocks(event_loop) -> None:
    # Arrange
    lines = [
        _line({"type": "system", "subtype": "init"}),
        _line(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "world"},
                    ]
                },
            }
        ),
        _line({"type": "result", "subtype": "success", "result": "Hello world"}),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert — assistant blocks yielded, result duplicate suppressed
    assert result == ["Hello ", "world"]


@pytest.mark.unit
def test_stream_event_deltas_then_result_yields_tokens(event_loop) -> None:
    # Arrange
    lines = [
        _line({"type": "system", "subtype": "init"}),
        _line(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hi "},
                },
            }
        ),
        _line(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "there"},
                },
            }
        ),
        _line({"type": "stream_event", "event": {"type": "content_block_stop"}}),
        _line({"type": "result", "subtype": "success", "result": "Hi there"}),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert
    assert result == ["Hi ", "there"]


@pytest.mark.unit
def test_result_only_fallback_when_no_assistant(event_loop) -> None:
    # Arrange — some older/edge paths only emit a terminal result event
    lines = [
        _line({"type": "system", "subtype": "init"}),
        _line({"type": "result", "subtype": "success", "result": "final answer"}),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert
    assert result == ["final answer"]


@pytest.mark.unit
def test_error_event_raises(event_loop) -> None:
    # Arrange
    lines = [
        _line({"type": "system", "subtype": "init"}),
        _line({"type": "error", "message": "boom"}),
    ]
    stream = _FakeStream(lines)

    # Act + Assert
    with pytest.raises(ClaudeCodeError, match="boom"):
        event_loop.run_until_complete(
            _collect(_parse_stream(stream, timeout_s=5))
        )


@pytest.mark.unit
def test_result_error_subtype_raises(event_loop) -> None:
    lines = [
        _line({"type": "result", "subtype": "error", "error": "rate limited"}),
    ]
    stream = _FakeStream(lines)

    with pytest.raises(ClaudeCodeError, match="rate limited"):
        event_loop.run_until_complete(
            _collect(_parse_stream(stream, timeout_s=5))
        )


@pytest.mark.unit
def test_unknown_event_type_does_not_crash(event_loop) -> None:
    # Arrange
    lines = [
        _line({"type": "brand_new_future_event", "payload": {"x": 1}}),
        _line(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "ok"}]},
            }
        ),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert
    assert result == ["ok"]


@pytest.mark.unit
def test_system_and_user_events_are_ignored(event_loop) -> None:
    # Arrange — tool echo from ``user`` events must not leak to channel
    lines = [
        _line({"type": "system", "subtype": "hook_started"}),
        _line({"type": "user", "message": {"content": [{"type": "tool_result"}]}}),
        _line({"type": "rate_limit_event", "rate_limit_info": {}}),
        _line(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "hi"}]},
            }
        ),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert
    assert result == ["hi"]


@pytest.mark.unit
def test_legacy_text_and_content_block_delta_still_work(event_loop) -> None:
    # Arrange — older/legacy event shapes
    lines = [
        _line({"type": "text", "text": "A"}),
        _line({"type": "content_block_delta", "delta": "B"}),
    ]
    stream = _FakeStream(lines)

    # Act
    result = event_loop.run_until_complete(
        _collect(_parse_stream(stream, timeout_s=5))
    )

    # Assert
    assert result == ["A", "B"]
