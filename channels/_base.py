"""Channel Protocol — contract every channel adapter satisfies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Protocol


@dataclass(frozen=True)
class InboundMessage:
    """Normalized inbound message from any channel."""

    channel: str
    chat_id: str
    sender_id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Widget:
    """Normalized outbound payload. Channels render per their capabilities."""

    type: Literal["text", "file", "quiz_url", "flashcard_url"]
    content: str


MessageHandler = Callable[[InboundMessage], Awaitable[None]]


class Channel(Protocol):
    """Structural channel type — bring your own transport."""

    async def start(self, handler: MessageHandler) -> None: ...

    async def stop(self) -> None: ...

    async def send(self, chat_id: str, widget: Widget) -> None: ...
