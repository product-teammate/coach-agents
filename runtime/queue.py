"""Per-user FIFO queues so only one brain subprocess is in flight per user."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class _UserQueue:
    queue: asyncio.Queue
    task: asyncio.Task


class PerUserQueueManager:
    """Route work to per-user asyncio queues; one worker per user."""

    def __init__(self) -> None:
        self._queues: dict[str, _UserQueue] = {}

    async def submit(
        self,
        user_key: str,
        work: Callable[[], Awaitable[None]],
    ) -> None:
        """Enqueue a coroutine factory for this user's queue."""
        if user_key not in self._queues:
            q: asyncio.Queue = asyncio.Queue()
            task = asyncio.create_task(self._worker(user_key, q))
            self._queues[user_key] = _UserQueue(queue=q, task=task)
        await self._queues[user_key].queue.put(work)

    async def _worker(self, user_key: str, q: asyncio.Queue) -> None:
        while True:
            work = await q.get()
            try:
                await work()
            except Exception:  # noqa: BLE001 — never let one turn kill the worker
                # A real runtime logs via loguru; tests patch this.
                continue
            finally:
                q.task_done()

    async def close(self) -> None:
        for uq in self._queues.values():
            uq.task.cancel()
        self._queues.clear()
