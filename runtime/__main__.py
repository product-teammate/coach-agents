"""``python -m runtime`` — entry point for starting the coach runtime.

Loads every agent (or the single one named in ``COACH_ONLY_AGENT``),
starts each enabled channel, wires the Claude Code brain through the
router, and schedules heartbeat jobs for agents that opted in.
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from loguru import logger

from brains._base import BrainInvocation
from brains.claude_code.adapter import ClaudeCodeBrain
from channels._base import Widget
from channels.cli.adapter import CLIChannel
from channels.slack.adapter import SlackChannel
from channels.telegram.adapter import TelegramChannel
from runtime.env import load_dotenv
from runtime.loader import LoadedAgent, discover_agents
from runtime.onboarding import run_onboarding_tick
from runtime.cron_loader import CronEntry, parse_cron_file, reconcile
from runtime.permissions import merge_tools
from runtime.queue import PerUserQueueManager
from runtime.router import Router
from runtime.scheduler import CoachScheduler


CRON_POLL_INTERVAL_S = int(os.environ.get("COACH_CRON_POLL_S", "60"))


def _build_channel(agent: LoadedAgent, ch_cfg: dict):  # noqa: ANN401 — factory
    """Construct a channel adapter from its YAML block, or return None."""
    ctype = ch_cfg.get("type")
    if ctype == "telegram":
        return TelegramChannel(
            agent_id=agent.agent_id,
            env_prefix=ch_cfg.get("env_prefix", ""),
            allow_from=ch_cfg.get("allow_from", []),
        )
    if ctype == "slack":
        return SlackChannel(
            agent_id=agent.agent_id,
            env_prefix=ch_cfg.get("env_prefix", ""),
            allow_from=ch_cfg.get("allow_from", []),
            group_policy=ch_cfg.get("group_policy", "mention"),
            group_allow_from=ch_cfg.get("group_allow_from", []),
            reply_in_thread=ch_cfg.get("reply_in_thread", True),
            react_emoji=ch_cfg.get("react_emoji", "eyes"),
        )
    if ctype == "cli":
        return CLIChannel(agent_id=agent.agent_id)
    logger.warning(
        "skipping unsupported channel {} for agent {}", ctype, agent.agent_id
    )
    return None


def _primary_channel(agent: LoadedAgent, started: dict[str, object]):
    """Return the first started channel for the agent (for heartbeats)."""
    return started.get(agent.agent_id)


def _heartbeat_content(agent: LoadedAgent) -> str | None:
    """Return the actionable content of HEARTBEAT.md, or ``None`` if empty."""
    heartbeat_rel = (
        (agent.config.get("proactive") or {}).get("heartbeat", {}).get("file")
        or "HEARTBEAT.md"
    )
    path = agent.directory / heartbeat_rel
    if not path.exists():
        return None
    out_lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("<!--"):
            continue
        if line.startswith("*") and line.endswith("*"):
            # italic template prose
            continue
        out_lines.append(raw)
    body = "\n".join(out_lines).strip()
    return body or None


def _make_heartbeat_job(
    agent: LoadedAgent,
    brain: ClaudeCodeBrain,
    channel,
) -> "callable":  # type: ignore[type-arg]
    """Build a zero-arg async job that fires a synthetic heartbeat turn."""

    brain_cfg = agent.config.get("brain", {})

    async def _tick() -> None:
        # ORDER: ONBOARDING.md first, then the recurring HEARTBEAT.md work.
        # Onboarding clears out one-shot setup tasks (like knowledge pre-load)
        # before the recurring routine runs.
        try:
            executed = await run_onboarding_tick(agent, brain)
            if executed:
                logger.info(
                    "onboarding[{}] executed {} task(s)",
                    agent.agent_id,
                    executed,
                )
        except Exception:  # noqa: BLE001
            logger.exception("onboarding[{}] tick failed", agent.agent_id)

        content = _heartbeat_content(agent)
        if content is None:
            logger.info("heartbeat[{}] tick: no tasks", agent.agent_id)
            return
        system_prompt = (
            "Execute the following periodic tasks from HEARTBEAT.md\n\n"
            + content
        )
        inv = BrainInvocation(
            agent_dir=agent.directory,
            user_message=system_prompt,
            session_id=f"heartbeat:{agent.agent_id}",
            allowed_tools=merge_tools(
                brain_cfg.get("allowed_tools") or [], agent.skills
            ),
            model=brain_cfg.get("model"),
            timeout_s=int(brain_cfg.get("timeout_s") or 120),
            permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
        )
        buffer: list[str] = []
        async for chunk in brain.invoke(inv):
            buffer.append(chunk)
        reply = "".join(buffer).strip()
        if not reply:
            logger.info("heartbeat[{}] produced empty reply", agent.agent_id)
            return
        try:
            # Heartbeat targets the owner via the first chat the channel knows;
            # for Phase 1 we post to a configured channel id if present.
            target = (
                (agent.config.get("proactive") or {})
                .get("heartbeat", {})
                .get("target_chat_id")
            )
            if target is None:
                logger.info(
                    "heartbeat[{}]: no target_chat_id configured; skipping send",
                    agent.agent_id,
                )
                return
            await channel.send(target, Widget(type="text", content=reply))
        except Exception:  # noqa: BLE001
            logger.exception("heartbeat[{}] send failed", agent.agent_id)

    return _tick


def _make_cron_job(
    agent: LoadedAgent,
    brain: ClaudeCodeBrain,
    channel,
    entry: CronEntry,
):  # type: ignore[no-untyped-def]
    """Build a zero-arg async callable that fires one cron turn."""
    brain_cfg = agent.config.get("brain", {})

    async def _fire() -> None:
        inv = BrainInvocation(
            agent_dir=agent.directory,
            user_message=f"Scheduled task ({entry.cron_expr}): {entry.task}",
            session_id=f"cron:{agent.agent_id}:{entry.job_id}",
            allowed_tools=merge_tools(
                brain_cfg.get("allowed_tools") or [], agent.skills
            ),
            model=brain_cfg.get("model"),
            timeout_s=int(brain_cfg.get("timeout_s") or 120),
            permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
        )
        buffer: list[str] = []
        async for chunk in brain.invoke(inv):
            buffer.append(chunk)
        reply = "".join(buffer).strip()
        if not reply:
            logger.info(
                "cron[{}:{}] produced empty reply", agent.agent_id, entry.job_id
            )
            return
        try:
            await channel.send(entry.target, Widget(type="text", content=reply))
        except Exception:  # noqa: BLE001
            logger.exception(
                "cron[{}:{}] send failed", agent.agent_id, entry.job_id
            )

    return _fire


def _setup_cron_reload(
    agent: LoadedAgent,
    brain: ClaudeCodeBrain,
    channel,
    scheduler: CoachScheduler,
    poll_interval_s: int = CRON_POLL_INTERVAL_S,
) -> None:
    """Register initial cron jobs and a polling job that reconciles on file change."""
    cron_path = agent.directory / "CRON.md"
    registered: dict[str, CronEntry] = {}

    def _add(job_id: str, cron_expr: str, cb) -> None:  # type: ignore[no-untyped-def]
        scheduler.add_cron(agent.agent_id, job_id, cron_expr, cb)

    def _remove(job_id: str) -> None:
        scheduler.remove_job(f"{agent.agent_id}:{job_id}")

    def _make_cb(entry: CronEntry):  # type: ignore[no-untyped-def]
        return _make_cron_job(agent, brain, channel, entry)

    def _tick_once() -> None:
        entries = parse_cron_file(cron_path)
        reconcile(agent.agent_id, entries, registered, _add, _remove, _make_cb)

    _tick_once()

    async def _poll() -> None:
        try:
            _tick_once()
        except Exception:  # noqa: BLE001
            logger.exception("cron[{}] reload failed", agent.agent_id)

    scheduler.add_interval(
        f"cron-reload:{agent.agent_id}", poll_interval_s, _poll
    )
    logger.info(
        "cron[{}] reload poller active every {}s",
        agent.agent_id,
        poll_interval_s,
    )


async def _run() -> None:
    load_dotenv()
    agents = discover_agents()
    if not agents:
        print("no agents found; run `coach new <id>` to scaffold one.")
        return

    queue = PerUserQueueManager()
    brain = ClaudeCodeBrain()
    scheduler = CoachScheduler()
    routers: list[Router] = []
    channels: list = []
    primary_by_agent: dict[str, object] = {}

    for agent in agents:
        for ch_cfg in agent.config.get("channels", []):
            if not ch_cfg.get("enabled"):
                continue
            channel = _build_channel(agent, ch_cfg)
            if channel is None:
                continue
            router = Router(agent=agent, brain=brain, channel=channel, queue=queue)
            routers.append(router)
            channels.append(channel)
            primary_by_agent.setdefault(agent.agent_id, channel)
            try:
                await channel.start(router.on_message)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "failed to start channel {} for {}",
                    ch_cfg.get("type"),
                    agent.agent_id,
                )

    # Schedule heartbeats.
    for agent in agents:
        proactive = agent.config.get("proactive") or {}
        heartbeat = proactive.get("heartbeat") or {}
        if heartbeat.get("enabled"):
            interval = int(heartbeat.get("interval_s") or 1800)
            channel = _primary_channel(agent, primary_by_agent)
            if channel is None:
                logger.warning(
                    "heartbeat[{}] enabled but no channel running; skipping",
                    agent.agent_id,
                )
            else:
                job = _make_heartbeat_job(agent, brain, channel)
                scheduler.add_heartbeat(agent.agent_id, interval, job)
                logger.info(
                    "heartbeat[{}] scheduled every {}s", agent.agent_id, interval
                )
        cron = proactive.get("cron") or {}
        if cron.get("enabled"):
            channel = _primary_channel(agent, primary_by_agent)
            if channel is None:
                logger.warning(
                    "cron[{}] enabled but no channel running; skipping",
                    agent.agent_id,
                )
            else:
                _setup_cron_reload(agent, brain, channel, scheduler)

    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            # Not all platforms/event loops support this.
            pass
    await stop.wait()

    for channel in channels:
        try:
            await channel.stop()
        except Exception:  # noqa: BLE001
            logger.exception("error stopping channel")
    scheduler.shutdown()
    await queue.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()


# Silence the unused-import warning for Path (retained for type hints
# inside factory helpers defined at module scope).
_ = Path
