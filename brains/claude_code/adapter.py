"""Spawn the `claude` CLI as a subprocess and stream its output.

The ``claude`` CLI (2.x) in ``--output-format stream-json`` mode emits
several event types. This adapter parses them and yields only the
textual assistant output so the caller can forward it to a channel.

Event types handled:
    system        - init/hook lifecycle; ignored.
    assistant     - full assistant message; yield all text blocks.
    stream_event  - partial streaming; yield text_delta tokens.
    user          - echoed tool results; ignored.
    result        - terminal event with final ``result`` string; used as
                    a fallback when nothing was streamed.
    error         - fatal; raises :class:`ClaudeCodeError`.

Older event types (``text`` / ``content_block_delta`` at the top level)
are still supported for backward compatibility.

If ``COACH_BRAIN_STUB=1`` is set the brain returns a canned stub so
tests and smoke checks can run without the ``claude`` CLI installed.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator

from loguru import logger

from pathlib import Path

from brains._base import BrainInvocation
from brains.claude_code.session import session_uuid
from observability import get_emitter


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
        sid = session_uuid(inv.agent_dir, inv.session_id)
        # claude CLI stores sessions at ~/.claude/projects/<cwd-hash>/<sid>.jsonl.
        # If the file exists, this is a continuation → use --resume. Otherwise
        # first turn → use --session-id to mint it.
        cwd_hash = str(inv.agent_dir.resolve()).replace("/", "-")
        session_file = (
            Path.home() / ".claude" / "projects" / cwd_hash / f"{sid}.jsonl"
        )
        session_flag = ["--resume", sid] if session_file.exists() else ["--session-id", sid]
        args = [
            self._binary,
            "-p",
            inv.user_message,
            *session_flag,
            "--output-format",
            "stream-json",
            "--permission-mode",
            inv.permission_mode,
            "--verbose",
        ]
        if inv.allowed_tools:
            args += ["--allowed-tools", ",".join(inv.allowed_tools)]
        if inv.model:
            args += ["--model", inv.model]
        if inv.effort:
            args += ["--effort", inv.effort]

        # Expose the project-local skills plugin if present.
        # agent_dir = <project_root>/agents/<id>; walk two parents up.
        project_root = inv.agent_dir.resolve().parent.parent
        if (project_root / ".claude-plugin" / "plugin.json").exists():
            args += ["--plugin-dir", str(project_root)]

        logger.debug("claude_code spawn: {}", " ".join(args))

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(inv.agent_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert proc.stdout is not None
        assert proc.stderr is not None

        emitter = get_emitter()
        rid = inv.request_id
        if rid:
            emitter.event(
                rid,
                "brain_spawn",
                {
                    "argv": args,
                    "pid": proc.pid,
                    "cwd": str(inv.agent_dir),
                    "binary": self._binary,
                    "session_id_claude": sid,
                },
            )

        stderr_chunks: list[bytes] = []

        async def _drain_stderr() -> None:
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    return
                stderr_chunks.append(chunk)

        stderr_task = asyncio.create_task(_drain_stderr())

        try:
            async for chunk in _parse_stream(
                proc.stdout,
                timeout_s=inv.timeout_s,
                emitter=emitter if rid else None,
                request_id=rid,
            ):
                yield chunk
        finally:
            if proc.returncode is None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        proc.kill()
            try:
                await asyncio.wait_for(stderr_task, timeout=2)
            except asyncio.TimeoutError:
                stderr_task.cancel()

            stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
            if proc.returncode and proc.returncode != 0:
                logger.error(
                    "claude_code exit={} stderr={}",
                    proc.returncode,
                    stderr_text[:2000] or "<empty>",
                )
            elif stderr_text:
                logger.debug("claude_code stderr: {}", stderr_text[:500])


async def _parse_stream(
    stream: asyncio.StreamReader,
    *,
    timeout_s: int,
    emitter: Any = None,
    request_id: str | None = None,
) -> AsyncIterator[str]:
    """Parse stream-json events and yield user-visible text."""

    yielded_anything = False
    assistant_text_seen = False

    async for line in _read_lines(stream, timeout_s=timeout_s):
        event = _parse_event(line)
        if event is None:
            continue
        etype = event.get("type")

        if emitter and request_id:
            emitter.event(request_id, f"stream:{etype or 'unknown'}", event)

        if etype == "assistant":
            message = event.get("message") or {}
            for block in message.get("content") or []:
                if block.get("type") == "text":
                    text = block.get("text") or ""
                    if text:
                        assistant_text_seen = True
                        yielded_anything = True
                        yield text

        elif etype == "stream_event":
            inner = event.get("event") or {}
            if inner.get("type") == "content_block_delta":
                delta = inner.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        assistant_text_seen = True
                        yielded_anything = True
                        yield text

        elif etype == "result":
            subtype = event.get("subtype")
            if emitter and request_id:
                try:
                    emitter.update_usage(
                        request_id,
                        usage=event.get("usage") or {},
                        cost_usd=event.get("total_cost_usd"),
                        num_turns=event.get("num_turns"),
                    )
                except Exception:  # noqa: BLE001
                    pass
            if subtype == "success":
                # Only use as fallback when nothing was streamed/assistant-ed
                if not assistant_text_seen:
                    text = event.get("result") or ""
                    if text:
                        yielded_anything = True
                        yield text
            elif subtype == "error" or subtype == "error_max_turns":
                raise ClaudeCodeError(
                    event.get("error") or event.get("result") or "claude CLI error"
                )

        elif etype == "error":
            raise ClaudeCodeError(
                event.get("message") or event.get("error") or "claude CLI error"
            )

        elif etype in {"text", "content_block_delta"}:
            # Backward-compatible legacy event shapes.
            delta = event.get("delta") or event.get("text") or ""
            if delta:
                yielded_anything = True
                yield delta

        elif etype in {"system", "user", "rate_limit_event"}:
            # Lifecycle / tool-echo / metadata; not user-facing.
            continue

        else:
            logger.debug(
                "claude_code adapter: unknown event type={} raw={}",
                etype,
                line[:200],
            )

    if not yielded_anything:
        logger.debug("claude_code adapter: stream ended with no text yielded")


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


def _parse_event(raw: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None
