"""`python -m runtime` — entry point for starting the coach runtime.

Phase 1: loads agents, starts their channels, wires the Claude Code brain,
and blocks on the event loop. This is intentionally minimal; richer
orchestration (multi-brain, multi-channel fan-out, heartbeat integration)
is layered on as skills mature.
"""

from __future__ import annotations

import asyncio
import signal

from brains.claude_code.adapter import ClaudeCodeBrain
from channels.cli.adapter import CLIChannel
from channels.telegram.adapter import TelegramChannel
from runtime.env import load_dotenv
from runtime.loader import discover_agents
from runtime.queue import PerUserQueueManager
from runtime.router import Router


async def _run() -> None:
    load_dotenv()
    agents = discover_agents()
    if not agents:
        print("no agents found; run `coach new <id>` to scaffold one.")
        return

    queue = PerUserQueueManager()
    brain = ClaudeCodeBrain()
    routers: list[Router] = []
    channels: list = []

    for agent in agents:
        for ch_cfg in agent.config.get("channels", []):
            if not ch_cfg.get("enabled"):
                continue
            ctype = ch_cfg.get("type")
            if ctype == "telegram":
                channel = TelegramChannel(
                    agent_id=agent.agent_id,
                    env_prefix=ch_cfg.get("env_prefix", ""),
                    allow_from=ch_cfg.get("allow_from", []),
                )
            elif ctype == "cli":
                channel = CLIChannel(agent_id=agent.agent_id)
            else:
                print(f"skipping unsupported channel {ctype} for {agent.agent_id}")
                continue
            router = Router(agent=agent, brain=brain, channel=channel, queue=queue)
            routers.append(router)
            channels.append(channel)
            await channel.start(router.on_message)

    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    for channel in channels:
        await channel.stop()
    await queue.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
