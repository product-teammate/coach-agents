"""`coach start <agent_id>` — run the runtime."""

from __future__ import annotations

import os
import subprocess
import sys

import typer
from rich.console import Console


console = Console()


def start(
    agent: str = typer.Argument(None, help="Agent id. Omit with --all to run every agent."),
    all_agents: bool = typer.Option(False, "--all", help="Start every agent."),
) -> None:
    """Phase 1: shell out to `python -m runtime`.

    We don't yet support filtering by agent id — the runtime loads every
    discovered agent. `--all` is accepted for forward compatibility.
    """
    if not agent and not all_agents:
        raise typer.BadParameter("provide an agent id or pass --all")

    if agent and not all_agents:
        console.print(
            f"[yellow]note:[/] Phase 1 runtime starts every discovered agent; "
            f"pass --all to acknowledge. Requested agent: {agent}"
        )

    env = os.environ.copy()
    proc = subprocess.run([sys.executable, "-m", "runtime"], env=env)
    raise typer.Exit(code=proc.returncode)
