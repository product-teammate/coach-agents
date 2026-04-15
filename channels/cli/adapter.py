"""Terminal REPL channel — reads stdin, prints stdout.

Useful for developing an agent without connecting any chat app.
"""

from __future__ import annotations

import asyncio
import sys

from channels._base import Channel, InboundMessage, MessageHandler, Widget


class CLIChannel:
    """Read lines from stdin, dispatch to the handler, print widgets."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._running = False
        self._handler: MessageHandler | None = None

    async def start(self, handler: MessageHandler) -> None:
        self._handler = handler
        self._running = True
        loop = asyncio.get_event_loop()
        while self._running:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            text = line.rstrip("\n")
            if not text:
                continue
            inbound = InboundMessage(
                channel="cli",
                chat_id="local",
                sender_id="local",
                text=text,
                metadata={},
            )
            await handler(inbound)

    async def stop(self) -> None:
        self._running = False

    async def send(self, chat_id: str, widget: Widget) -> None:
        sys.stdout.write(f"[{widget.type}] {widget.content}\n")
        sys.stdout.flush()
