"""APScheduler-backed job runner for heartbeat + cron skills.

Phase 1: in-memory JobStore. Per-agent SQLite persistence comes later.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class ScheduledJob:
    """Minimal job descriptor."""

    job_id: str
    agent_id: str
    when: str                       # ISO datetime or cron expression
    callback: Callable[[], Awaitable[None]]


class CoachScheduler:
    """Thin wrapper over APScheduler for testability.

    Imports APScheduler lazily so the rest of the runtime can be exercised
    without pulling in the dependency.
    """

    def __init__(self) -> None:
        self._scheduler = None  # type: ignore[assignment]

    def _ensure(self) -> None:
        if self._scheduler is not None:
            return
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

    def add_heartbeat(
        self,
        agent_id: str,
        interval_s: int,
        callback: Callable[[], Awaitable[None]],
    ) -> ScheduledJob:
        self._ensure()
        assert self._scheduler is not None
        job = self._scheduler.add_job(
            callback,
            "interval",
            seconds=interval_s,
            id=f"heartbeat:{agent_id}",
            replace_existing=True,
        )
        return ScheduledJob(
            job_id=job.id, agent_id=agent_id, when=f"every {interval_s}s", callback=callback
        )

    def add_cron(
        self,
        agent_id: str,
        job_id: str,
        cron_expr: str,
        callback: Callable[[], Awaitable[None]],
    ) -> ScheduledJob:
        self._ensure()
        assert self._scheduler is not None
        from apscheduler.triggers.cron import CronTrigger  # type: ignore

        trigger = CronTrigger.from_crontab(cron_expr)
        job = self._scheduler.add_job(
            callback, trigger, id=f"{agent_id}:{job_id}", replace_existing=True
        )
        return ScheduledJob(
            job_id=job.id, agent_id=agent_id, when=cron_expr, callback=callback
        )

    def add_interval(
        self,
        job_id: str,
        interval_s: int,
        callback: Callable[[], Awaitable[None]],
    ) -> ScheduledJob:
        """Register a plain interval job (not tied to an agent heartbeat)."""
        self._ensure()
        assert self._scheduler is not None
        job = self._scheduler.add_job(
            callback,
            "interval",
            seconds=interval_s,
            id=job_id,
            replace_existing=True,
        )
        return ScheduledJob(
            job_id=job.id,
            agent_id="<runtime>",
            when=f"every {interval_s}s",
            callback=callback,
        )

    def remove_job(self, job_id: str) -> None:
        """Remove a previously-registered job; silent if it does not exist."""
        if self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(job_id)
        except Exception:  # noqa: BLE001 — APScheduler raises JobLookupError
            pass

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
