"""Parse ``agents/<id>/CRON.md`` and register jobs with the scheduler.

Line format (one per ``## Active`` body line):

    - [<cron-expr>] <task description> → target: <chat_id> (added <ISO>)

The cron expression is a standard 5-field crontab string. Anything after
the closing ``]`` up to the ``→`` arrow is the task body. The ``target:``
token names a Slack channel id, Telegram chat id, or the literal ``dm``.

Supports a hot-reload polling job that diffs parsed lines against the
currently-registered cron jobs every ``poll_interval_s`` seconds.
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


CRON_LINE = re.compile(
    r"^\s*-\s*\[(?P<cron>[^\]]+)\]\s*(?P<task>.+?)\s*(?:\u2192|->)\s*target:\s*(?P<target>\S+)"
)


@dataclass(frozen=True)
class CronEntry:
    """One parsed line from CRON.md."""

    cron_expr: str
    task: str
    target: str

    @property
    def job_id(self) -> str:
        # Stable, deterministic id for APScheduler de-dup.
        safe = re.sub(r"\W+", "_", f"{self.cron_expr}|{self.task}|{self.target}")
        return f"cron:{safe}"[:180]


def parse_cron_file(path: Path) -> list[CronEntry]:
    """Return every entry under the ``## Active`` section."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[CronEntry] = []
    in_active = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            in_active = stripped[3:].strip().lower() == "active"
            continue
        if not in_active or not stripped:
            continue
        m = CRON_LINE.match(raw)
        if not m:
            continue
        try:
            from croniter import croniter  # type: ignore
            if not croniter.is_valid(m["cron"].strip()):
                logger.warning("cron: invalid expression {!r}", m["cron"])
                continue
        except ImportError:
            pass
        entries.append(
            CronEntry(
                cron_expr=m["cron"].strip(),
                task=m["task"].strip(),
                target=m["target"].strip(),
            )
        )
    return entries


def reconcile(
    agent_id: str,
    entries: list[CronEntry],
    registered: dict[str, CronEntry],
    add: Callable[[str, str, Callable[[], Awaitable[None]]], None],
    remove: Callable[[str], None],
    make_callback: Callable[[CronEntry], Callable[[], Awaitable[None]]],
) -> tuple[int, int]:
    """Diff ``entries`` (desired) against ``registered`` (current).

    Returns ``(added, removed)`` counts. ``registered`` is mutated in place.
    """
    desired = {e.job_id: e for e in entries}

    added = 0
    for job_id, entry in desired.items():
        if job_id not in registered:
            add(job_id, entry.cron_expr, make_callback(entry))
            registered[job_id] = entry
            added += 1
            logger.info(
                "cron[{}] +{} {!r} -> {}",
                agent_id,
                entry.cron_expr,
                entry.task,
                entry.target,
            )

    removed = 0
    for job_id in list(registered):
        if job_id not in desired:
            remove(job_id)
            registered.pop(job_id, None)
            removed += 1
            logger.info("cron[{}] -{}", agent_id, job_id)

    return added, removed
