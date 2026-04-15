"""Spawn the `claude` CLI as a subprocess and stream its output.

Phase 1 target: a minimal, working adapter that either

1. Spawns `claude -p <prompt> --session <path> --output-format stream-json
   --permission-mode <mode> --allowed-tools <csv>` and parses its stream,
   yielding text deltas to the caller, OR
2. Returns a canned stub response when `COACH_BRAIN_STUB=1` is set, so
   tests and smoke checks can run without the `claude` CLI installed.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

from brains._base import BrainInvocation
from brains.claude_code.session import session_path


class ClaudeCodeError(RuntimeError):
    """Raised when the claude CLI emits an error event or exits non-zero."""


class ClaudeCodeBrain:
    """Brain adapter backed by the `claude` CLI."""

    def __init__(self, binary: str = "claude") -> None:
        self._binary = binary

    async def invoke(self, inv: BrainInvocation) -> AsyncIterator[str]:
        if os.environ.get("COACH_BRAIN_STUB") == "1":
            async for chunk in self._stub(inv):
                yield chunk
            return

        async for chunk in self._spawn(inv):
            yield chunk

    async def _stub(self, inv: BrainInvocation) -> AsyncIterator[str]:
        yield f"[stub] received: {inv.user_message}"

    async def _spawn(self, inv: BrainInvocation) -> AsyncIterator[str]:
        session_file = session_path(inv.agent_dir, inv.session_id)
        args = [
            self._binary,
            "-p",
            inv.user_message,
            "--session",
            str(session_file),
            "--output-format",
            "stream-json",
            "--permission-mode",
            inv.permission_mode,
        ]
        if inv.allowed_tools:
            args += ["--allowed-tools", ",".join(inv.allowed_tools)]
        if inv.model:
            args += ["--model", inv.model]

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(inv.agent_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert proc.stdout is not None
        try:
            async for line in _read_lines(proc.stdout, timeout_s=inv.timeout_s):
                event = _parse_event(line)
                if event is None:
                    continue
                etype = event.get("type")
                if etype in {"text", "content_block_delta"}:
                    delta = event.get("delta") or event.get("text") or ""
                    if delta:
                        yield delta
                elif etype == "error":
                    raise ClaudeCodeError(event.get("message", "unknown error"))
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()


async def _read_lines(
    stream: asyncio.StreamReader, *, timeout_s: int
) -> AsyncIterator[bytes]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise ClaudeCodeError(f"timed out after {timeout_s}s")
        try:
            line = await asyncio.wait_for(stream.readline(), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise ClaudeCodeError(f"timed out after {timeout_s}s") from exc
        if not line:
            return
        yield line


def _parse_event(raw: bytes) -> dict | None:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
