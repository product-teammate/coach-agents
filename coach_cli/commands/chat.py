"""``coach chat <agent> "msg"`` — simulate an inbound message offline.

Bypasses Slack/Telegram and invokes the brain directly. Useful for
manual testing and as the primitive the eval runner reuses.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import typer
import yaml
from loguru import logger

from brains._base import BrainInvocation
from brains.advise_mode import build as build_advise_prompt
from brains.claude_code.adapter import ClaudeCodeBrain
from observability import get_emitter
from runtime.permissions import merge_tools


def _load_agent_yaml(agent_dir: Path) -> dict:
    cfg_path = agent_dir / "agent.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"no agent.yaml at {cfg_path}")
    return yaml.safe_load(cfg_path.read_text())


def _resolve_agent_dir(agent: str) -> Path:
    p = Path(agent)
    if p.is_dir() and (p / "agent.yaml").exists():
        return p.resolve()
    candidate = Path("agents") / agent
    if candidate.is_dir():
        return candidate.resolve()
    raise FileNotFoundError(f"agent '{agent}' not found")


def chat(
    agent: str = typer.Argument(..., help="Agent id (e.g. english-coach) or path"),
    message: str = typer.Argument(..., help="User message text"),
    session: str = typer.Option(
        "cli", "--session", "-s", help="Session tag; same value = same conversation"
    ),
    eval_tag: str | None = typer.Option(
        None, "--eval-tag", help="Tag request as part of an eval run"
    ),
    timeout: int = typer.Option(120, "--timeout", help="Max seconds"),
    stream: bool = typer.Option(True, "--stream/--no-stream"),
) -> None:
    """Send a message to AGENT and print the reply."""
    agent_dir = _resolve_agent_dir(agent)
    cfg = _load_agent_yaml(agent_dir)
    agent_id = cfg.get("agent", {}).get("id") or agent_dir.name

    brain_cfg = cfg.get("brain", {})
    skills = cfg.get("skills") or []

    emitter = get_emitter()
    session_id = f"cli:{session}"
    request_id = emitter.begin_request(
        agent=agent_id,
        channel="cli",
        chat_id=session,
        user_id="local",
        session_id=session_id,
        user_message=message,
        eval_tag=eval_tag,
        model=brain_cfg.get("model"),
    )

    inv = BrainInvocation(
        agent_dir=agent_dir,
        user_message=message,
        session_id=session_id,
        allowed_tools=merge_tools(brain_cfg.get("allowed_tools") or [], skills),
        model=brain_cfg.get("model"),
        timeout_s=timeout,
        permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
        request_id=request_id,
        append_system_prompt=build_advise_prompt(
            bool(brain_cfg.get("advise_mode"))
        ),
    )

    brain = ClaudeCodeBrain()

    async def _run() -> str:
        buf: list[str] = []
        status = "ok"
        err = None
        try:
            async for chunk in brain.invoke(inv):
                buf.append(chunk)
                if stream:
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            status = "error"
            err = repr(exc)
            logger.exception("brain error")
        combined = "".join(buf).strip()
        if not combined and status == "ok":
            status = "empty"
        emitter.finish_request(
            request_id,
            status=status,
            assistant_text=combined,
            error_tail=err,
        )
        if stream and combined:
            sys.stdout.write("\n")
        return combined

    reply = asyncio.run(_run())
    if not stream:
        typer.echo(reply or "(empty)")
    typer.echo(f"\n[request_id={request_id}]", err=True)
