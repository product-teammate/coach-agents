"""Slack channel adapter — Socket Mode via ``slack_sdk``.

Reads two env vars per agent (``<env_prefix>BOT_TOKEN`` and
``<env_prefix>APP_TOKEN``) and runs a Socket Mode client so no public
webhook is needed. Inbound events are normalized into :class:`InboundMessage`
and forwarded to the handler. Outbound :class:`Widget` payloads are
rendered via :mod:`channels.slack.widgets`.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from loguru import logger

from channels._base import Channel, InboundMessage, MessageHandler, Widget
from channels.slack.widgets import render_widget


class SlackChannel:
    """Socket-Mode Slack channel.

    Config:
        env_prefix: env var prefix, e.g. ``SLACK_ENGLISH_``. We read
            ``<prefix>BOT_TOKEN`` (``xoxb-``) and ``<prefix>APP_TOKEN`` (``xapp-``).
        allow_from: list of allowed Slack user ids, or ``["*"]`` for everyone.
        group_policy: ``open`` | ``mention`` | ``allowlist``. ``mention`` is
            the default for channel messages — the bot only replies when
            explicitly @mentioned.
        group_allow_from: list of channel ids to reply in when
            ``group_policy == "allowlist"``.
        reply_in_thread: when ``True`` (default), channel replies thread
            under the triggering message.
        react_emoji: emoji name (no colons) to react with on receipt.
    """

    def __init__(
        self,
        agent_id: str,
        env_prefix: str,
        allow_from: list[str] | None = None,
        group_policy: str = "mention",
        group_allow_from: list[str] | None = None,
        reply_in_thread: bool = True,
        react_emoji: str = "eyes",
    ) -> None:
        self.agent_id = agent_id
        self.env_prefix = env_prefix
        self.allow_from = list(allow_from or [])
        self.group_policy = group_policy
        self.group_allow_from = list(group_allow_from or [])
        self.reply_in_thread = reply_in_thread
        self.react_emoji = react_emoji

        self._web_client: Any | None = None
        self._socket_client: Any | None = None
        self._bot_user_id: str | None = None
        self._handler: MessageHandler | None = None
        self._running = False
        self._thread_ts_by_chat: dict[str, str] = {}

    # ---------------------------------------------------------------- env
    def _tokens(self) -> tuple[str, str]:
        bot_key = f"{self.env_prefix}BOT_TOKEN"
        app_key = f"{self.env_prefix}APP_TOKEN"
        bot = os.environ.get(bot_key)
        app = os.environ.get(app_key)
        if not bot or not app:
            raise RuntimeError(
                f"missing Slack tokens for agent {self.agent_id}: "
                f"set {bot_key} and {app_key}"
            )
        return bot, app

    # -------------------------------------------------------------- start
    async def start(self, handler: MessageHandler) -> None:
        from slack_sdk.socket_mode.aiohttp import SocketModeClient  # type: ignore
        from slack_sdk.socket_mode.request import SocketModeRequest  # type: ignore
        from slack_sdk.socket_mode.response import SocketModeResponse  # type: ignore
        from slack_sdk.web.async_client import AsyncWebClient  # type: ignore

        self._handler = handler
        bot_token, app_token = self._tokens()

        self._web_client = AsyncWebClient(token=bot_token)
        self._socket_client = SocketModeClient(
            app_token=app_token,
            web_client=self._web_client,
        )

        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = auth.get("user_id")
            logger.info(
                "slack[{}] connected as bot_user_id={}", self.agent_id, self._bot_user_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack[{}] auth_test failed: {}", self.agent_id, exc)

        async def _listener(
            client: "SocketModeClient",
            req: "SocketModeRequest",
        ) -> None:
            if req.type != "events_api":
                return
            await client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
            await self._dispatch_event(req.payload or {})

        self._socket_client.socket_mode_request_listeners.append(_listener)
        await self._socket_client.connect()
        self._running = True
        logger.info("slack[{}] Socket Mode connected", self.agent_id)

    # --------------------------------------------------------------- stop
    async def stop(self) -> None:
        self._running = False
        if self._socket_client is None:
            return
        try:
            await self._socket_client.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack[{}] close failed: {}", self.agent_id, exc)
        self._socket_client = None

    # --------------------------------------------------------------- send
    async def send(self, chat_id: str, widget: Widget) -> None:
        if self._web_client is None:
            raise RuntimeError(f"slack[{self.agent_id}] not started")

        rendered = render_widget(widget)
        thread_ts = self._thread_ts_by_chat.get(chat_id)
        if rendered.method == "post_message":
            payload = dict(rendered.payload)
            if thread_ts:
                payload.setdefault("thread_ts", thread_ts)
            await self._web_client.chat_postMessage(channel=chat_id, **payload)
        elif rendered.method == "upload_file":
            payload = dict(rendered.payload)
            if thread_ts:
                payload["thread_ts"] = thread_ts
            await self._web_client.files_upload_v2(channel=chat_id, **payload)
        else:
            raise ValueError(f"unknown rendered method: {rendered.method}")

    # ---------------------------------------------------------- internals
    async def _dispatch_event(self, payload: dict) -> None:
        event = payload.get("event") or {}
        event_type = event.get("type")
        if event_type not in ("message", "app_mention"):
            return
        if event.get("subtype"):
            return

        sender_id = event.get("user") or ""
        chat_id = event.get("channel") or ""
        text = event.get("text") or ""
        channel_type = event.get("channel_type") or ""

        if not sender_id or not chat_id:
            return
        if self._bot_user_id and sender_id == self._bot_user_id:
            return

        # Slack sends both ``message`` and ``app_mention`` for the same
        # mention — prefer ``app_mention``.
        if (
            event_type == "message"
            and self._bot_user_id
            and f"<@{self._bot_user_id}>" in text
        ):
            return

        if not self._is_allowed(sender_id):
            logger.debug(
                "slack[{}] sender {} not in allow_from", self.agent_id, sender_id
            )
            return

        if channel_type != "im" and not self._should_respond_in_channel(
            event_type, text, chat_id
        ):
            return

        clean = self._strip_bot_mention(text)

        # Compute thread_ts for the reply.
        thread_ts = event.get("thread_ts")
        if self.reply_in_thread and channel_type != "im" and not thread_ts:
            thread_ts = event.get("ts")
        if thread_ts and channel_type != "im":
            self._thread_ts_by_chat[chat_id] = thread_ts
        else:
            self._thread_ts_by_chat.pop(chat_id, None)

        # Best-effort :eyes: reaction.
        if self._web_client is not None and event.get("ts"):
            try:
                await self._web_client.reactions_add(
                    channel=chat_id,
                    name=self.react_emoji,
                    timestamp=event.get("ts"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("slack[{}] reactions_add failed: {}", self.agent_id, exc)

        inbound = InboundMessage(
            channel="slack",
            chat_id=chat_id,
            sender_id=sender_id,
            text=clean,
            metadata={
                "thread_ts": thread_ts,
                "channel_type": channel_type,
                "event_ts": event.get("ts"),
            },
        )
        if self._handler is None:
            return
        try:
            await self._handler(inbound)
        except Exception:  # noqa: BLE001
            logger.exception(
                "slack[{}] handler crashed for sender={}", self.agent_id, sender_id
            )

    def _is_allowed(self, sender_id: str) -> bool:
        if not self.allow_from:
            return True
        if "*" in self.allow_from:
            return True
        return sender_id in self.allow_from

    def _should_respond_in_channel(
        self, event_type: str, text: str, chat_id: str
    ) -> bool:
        if self.group_policy == "open":
            return True
        if self.group_policy == "mention":
            if event_type == "app_mention":
                return True
            return bool(
                self._bot_user_id and f"<@{self._bot_user_id}>" in text
            )
        if self.group_policy == "allowlist":
            return chat_id in self.group_allow_from
        return False

    def _strip_bot_mention(self, text: str) -> str:
        if not text or not self._bot_user_id:
            return text
        return re.sub(rf"<@{re.escape(self._bot_user_id)}>\s*", "", text).strip()


# Protocol conformance check (structural; not enforced at runtime).
_: type[Channel] = SlackChannel  # type: ignore[assignment]

# Silence unused-import warnings for the asyncio import (retained for
# future use in stop()/backpressure logic).
_ = asyncio
