"""Route inbound messages through a brain and back to the channel."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from brains._base import Brain, BrainInvocation
from channels._base import Channel, InboundMessage, Widget
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
        logger.info(
            "inbound chat_id={} agent={} text={!r}",
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
        )

        logger.info("brain invoke agent={} session={}", agent_id, session_id)
        buffer: list[str] = []
        chunks = 0
        async for chunk in self.brain.invoke(inv):
            buffer.append(chunk)
            chunks += 1
        combined = "".join(buffer).strip()
        logger.info(
            "brain done agent={} chunks={} total_chars={}",
            agent_id,
            chunks,
            len(combined),
        )

        if not combined:
            logger.warning(
                "brain returned empty response agent={} session={} — posting fallback",
                agent_id,
                session_id,
            )
            reply = EMPTY_REPLY_FALLBACK
        else:
            reply = combined

        await self.channel.send(msg.chat_id, Widget(type="text", content=reply))
