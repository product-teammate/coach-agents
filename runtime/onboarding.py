"""Consume ``ONBOARDING.md`` tasks before each heartbeat tick.

ONBOARDING.md is written by ``coach new`` when the user defers the
initial knowledge-base pre-load. On every heartbeat tick we look for
pending tasks and dispatch them:

* A task mentioning "Pre-load knowledge base" fires an AUTO ``coach
  learn`` run via :mod:`coach_cli.learn_core`.
* Any other pending bullet is sent to the brain as a regular user
  message so the agent can decide how to handle it.

Each completed task is moved from ``## Pending`` to ``## Completed`` with
a UTC timestamp. Once Pending is empty the file is renamed to
``ONBOARDING.done.md`` so we keep an audit trail without re-running.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from brains._base import Brain, BrainInvocation
from coach_cli.learn_core import (
    LearnRequest,
    finalize_learn,
    stream_learn,
)
from runtime.loader import LoadedAgent
from runtime.permissions import merge_tools


ONBOARDING_FILENAME = "ONBOARDING.md"
ONBOARDING_DONE_FILENAME = "ONBOARDING.done.md"

_PENDING_HEADER = "## Pending"
_COMPLETED_HEADER = "## Completed"
_TASK_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+)$")


@dataclass(frozen=True)
class OnboardingTask:
    """One parsed ``- [ ]`` bullet."""

    text: str


def _read_sections(text: str) -> tuple[list[str], list[str], list[str]]:
    """Split the file into (preamble, pending_block, completed_block) lines."""
    lines = text.splitlines()
    preamble: list[str] = []
    pending: list[str] = []
    completed: list[str] = []
    section: str = "preamble"
    for line in lines:
        if line.strip() == _PENDING_HEADER:
            section = "pending"
            continue
        if line.strip() == _COMPLETED_HEADER:
            section = "completed"
            continue
        if section == "preamble":
            preamble.append(line)
        elif section == "pending":
            pending.append(line)
        else:
            completed.append(line)
    return preamble, pending, completed


def parse_onboarding(path: Path) -> list[OnboardingTask]:
    """Return pending ``- [ ]`` tasks from ONBOARDING.md."""
    if not path.exists():
        return []
    _, pending, _ = _read_sections(path.read_text(encoding="utf-8"))
    tasks: list[OnboardingTask] = []
    for line in pending:
        m = _TASK_RE.match(line)
        if m:
            tasks.append(OnboardingTask(text=m.group(1).strip()))
    return tasks


def _render(
    preamble: list[str], pending: list[str], completed: list[str]
) -> str:
    parts: list[str] = []
    parts.extend(preamble)
    if parts and parts[-1] != "":
        parts.append("")
    parts.append(_PENDING_HEADER)
    parts.append("")
    parts.extend(pending)
    if not pending or pending[-1] != "":
        parts.append("")
    parts.append(_COMPLETED_HEADER)
    parts.append("")
    parts.extend(completed)
    return "\n".join(parts).rstrip() + "\n"


def mark_completed(path: Path, task_text: str) -> None:
    """Move a task from Pending to Completed with a UTC timestamp."""
    if not path.exists():
        return
    preamble, pending, completed = _read_sections(path.read_text(encoding="utf-8"))
    new_pending: list[str] = []
    ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    matched = False
    for line in pending:
        m = _TASK_RE.match(line)
        if m and m.group(1).strip() == task_text and not matched:
            completed.append(f"- [x] {task_text}  _(done {ts})_")
            matched = True
            continue
        new_pending.append(line)
    if matched:
        path.write_text(_render(preamble, new_pending, completed), encoding="utf-8")


def finalize_if_empty(path: Path) -> Path | None:
    """If no tasks remain pending, rename ONBOARDING.md -> ONBOARDING.done.md."""
    if not path.exists():
        return None
    remaining = parse_onboarding(path)
    if remaining:
        return None
    done = path.with_name(ONBOARDING_DONE_FILENAME)
    path.rename(done)
    return done


def is_preload_task(text: str) -> bool:
    return "pre-load knowledge base" in text.lower()


async def run_onboarding_tick(
    agent: LoadedAgent, brain: Brain
) -> int:
    """Process pending onboarding tasks. Returns the count executed."""
    path = agent.directory / ONBOARDING_FILENAME
    tasks = parse_onboarding(path)
    if not tasks:
        return 0

    executed = 0
    for task in tasks:
        try:
            if is_preload_task(task.text):
                await _run_preload(agent)
            else:
                await _run_generic_task(agent, brain, task.text)
            mark_completed(path, task.text)
            executed += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "onboarding[{}] task failed: {!r}", agent.agent_id, task.text
            )
            # Leave task pending so next tick retries.
    finalize_if_empty(path)
    return executed


async def _run_preload(agent: LoadedAgent) -> None:
    """Invoke an AUTO-mode learn run via the shared core."""
    req = LearnRequest(agent_id=agent.agent_id, mode="auto")
    buffer: list[str] = []
    async for chunk in stream_learn(req):
        buffer.append(chunk)
    logger.info(
        "onboarding[{}] preload complete ({} chars)",
        agent.agent_id,
        sum(len(c) for c in buffer),
    )
    finalize_learn(agent.agent_id)


async def _run_generic_task(
    agent: LoadedAgent, brain: Brain, task_text: str
) -> None:
    """Send an arbitrary task string to the brain as a user message."""
    brain_cfg = agent.config.get("brain", {})
    inv = BrainInvocation(
        agent_dir=agent.directory,
        user_message=f"[onboarding task]\n\n{task_text}",
        session_id=f"onboarding:{agent.agent_id}",
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
    logger.info(
        "onboarding[{}] generic task complete ({} chars)",
        agent.agent_id,
        sum(len(c) for c in buffer),
    )
