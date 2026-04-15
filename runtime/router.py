"""Route inbound messages through a brain and back to the channel."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from brains._base import Brain, BrainInvocation
from channels._base import Channel, InboundMessage, Widget
from observability import get_emitter
from runtime.loader import LoadedAgent
from runtime.permissions import merge_tools
from runtime.queue import PerUserQueueManager


EMPTY_REPLY_FALLBACK = (
    "I'm thinking but didn't produce a response. Try rephrasing?"
)


@dataclass
class Router:
    """Wires (agent, brain, channel) and handles per-turn orchestration."""

    agent: LoadedAgent
    brain: Brain
    channel: Channel
    queue: PerUserQueueManager

    async def on_message(self, msg: InboundMessage) -> None:
        await self.queue.submit(msg.sender_id, lambda: self._handle(msg))

    async def _handle(self, msg: InboundMessage) -> None:
        agent_id = self.agent.config.get("id") or self.agent.directory.name
        session_id = f"{msg.channel}:{msg.chat_id}"
        emitter = get_emitter()
        request_id = emitter.begin_request(
            agent=agent_id,
            channel=msg.channel,
            chat_id=msg.chat_id,
            user_id=msg.sender_id,
            session_id=session_id,
            user_message=msg.text or "",
        )
        logger.info(
            "inbound req={} chat_id={} agent={} text={!r}",
            request_id,
            msg.chat_id,
            agent_id,
            (msg.text or "")[:100],
        )

        brain_cfg = self.agent.config.get("brain", {})
        inv = BrainInvocation(
            agent_dir=self.agent.directory,
            user_message=msg.text,
            session_id=session_id,
            allowed_tools=merge_tools(
                brain_cfg.get("allowed_tools") or [],
                self.agent.skills,
            ),
            model=brain_cfg.get("model"),
            timeout_s=int(brain_cfg.get("timeout_s") or 120),
            permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
            request_id=request_id,
            effort=brain_cfg.get("effort"),
        )

        logger.info("brain invoke req={} agent={}", request_id, agent_id)
        buffer: list[str] = []
        chunks = 0
        status = "ok"
        error_tail = None
        try:
            async for chunk in self.brain.invoke(inv):
                buffer.append(chunk)
                chunks += 1
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error_tail = repr(exc)
            logger.exception("brain error req={}", request_id)

        combined = "".join(buffer).strip()
        logger.info(
            "brain done req={} chunks={} total_chars={}",
            request_id,
            chunks,
            len(combined),
        )

        if not combined and status == "ok":
            status = "empty"
            logger.warning(
                "brain returned empty response req={} — posting fallback",
                request_id,
            )
            reply = EMPTY_REPLY_FALLBACK
        else:
            reply = combined or EMPTY_REPLY_FALLBACK

        emitter.finish_request(
            request_id,
            status=status,
            assistant_text=combined,
            error_tail=error_tail,
        )

        await self.channel.send(msg.chat_id, Widget(type="text", content=reply))
