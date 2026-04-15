"""python-telegram-bot v21 adapter with long-polling."""

from __future__ import annotations

import os
from typing import Any

from channels._base import Channel, InboundMessage, MessageHandler, Widget
from channels.telegram.widgets import render_widget


class TelegramChannel:
    """Long-polling Telegram channel adapter.

    Reads the bot token from `<env_prefix>BOT_TOKEN`. Allowed senders are
    gated by `allow_from`; an empty list means "accept all" for dev use.
    """

    def __init__(
        self,
        agent_id: str,
        env_prefix: str,
        allow_from: list[int | str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.env_prefix = env_prefix
        self.allow_from = {str(x) for x in (allow_from or [])}
        self._application: Any | None = None

    def _token(self) -> str:
        key = f"{self.env_prefix}BOT_TOKEN"
        token = os.environ.get(key)
        if not token:
            raise RuntimeError(f"missing env var {key} for agent {self.agent_id}")
        return token

    async def start(self, handler: MessageHandler) -> None:
        # Lazy import so the package can be imported without PTB installed.
        from telegram import Update  # type: ignore
        from telegram.ext import (  # type: ignore
            Application,
            MessageHandler as PTBMessageHandler,
            filters,
        )

        app = Application.builder().token(self._token()).build()

        async def _on_message(update: Update, _ctx: Any) -> None:
            msg = update.effective_message
            if msg is None or msg.text is None:
                return
            sender_id = str(msg.from_user.id) if msg.from_user else "anon"
            if self.allow_from and sender_id not in self.allow_from:
                return
            inbound = InboundMessage(
                channel="telegram",
                chat_id=str(msg.chat_id),
                sender_id=sender_id,
                text=msg.text,
                metadata={"message_id": msg.message_id},
            )
            await handler(inbound)

        app.add_handler(PTBMessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
        self._application = app
        await app.initialize()
        await app.start()
        if app.updater is not None:
            await app.updater.start_polling()

    async def stop(self) -> None:
        if self._application is None:
            return
        app = self._application
        if app.updater is not None:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        self._application = None

    async def send(self, chat_id: str, widget: Widget) -> None:
        if self._application is None:
            raise RuntimeError("channel not started")
        rendered = render_widget(widget)
        method = getattr(self._application.bot, rendered["method"])
        await method(chat_id=chat_id, **rendered["payload"])
