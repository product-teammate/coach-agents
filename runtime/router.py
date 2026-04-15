"""Route inbound messages through a brain and back to the channel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brains._base import Brain, BrainInvocation
from channels._base import Channel, InboundMessage, Widget
from runtime.loader import LoadedAgent
from runtime.permissions import merge_tools
from runtime.queue import PerUserQueueManager


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
        brain_cfg = self.agent.config.get("brain", {})
        inv = BrainInvocation(
            agent_dir=self.agent.directory,
            user_message=msg.text,
            session_id=f"{msg.channel}:{msg.chat_id}",
            allowed_tools=merge_tools(
                brain_cfg.get("allowed_tools") or [],
                self.agent.skills,
            ),
            model=brain_cfg.get("model"),
            timeout_s=int(brain_cfg.get("timeout_s") or 120),
            permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
        )
        buffer: list[str] = []
        async for chunk in self.brain.invoke(inv):
            buffer.append(chunk)
        reply = "".join(buffer).strip() or "(no response)"
        await self.channel.send(msg.chat_id, Widget(type="text", content=reply))
