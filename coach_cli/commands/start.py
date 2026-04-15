"""``coach start [<agent_id>] [--all]`` — run the runtime."""

from __future__ import annotations

import os
import subprocess
import sys

import typer
from rich.console import Console

from runtime.loader import PROJECT_ROOT, discover_agents


console = Console()


def start(
    agent: str = typer.Argument(None, help="Agent id. Omit with --all to run every agent."),
    all_agents: bool = typer.Option(False, "--all", help="Start every agent."),
) -> None:
    """Start the coach runtime.

    Behavior:
      * ``coach start --all`` runs every discovered agent.
      * ``coach start <id>`` runs only that agent (via ``COACH_ONLY_AGENT``).
      * ``coach start`` with no args lists available agents and exits 0.
    """
    env = os.environ.copy()

    if not agent and not all_agents:
        try:
            discovered = [a.agent_id for a in discover_agents()]
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]failed to discover agents:[/] {exc}")
            raise typer.Exit(code=1) from exc
        if not discovered:
            console.print(
                "[yellow]no agents found.[/] Scaffold one with `coach new <id>`."
            )
            raise typer.Exit(code=0)
        console.print("Available agents:")
        for aid in discovered:
            console.print(f"  - {aid}")
        console.print(
            "Pass an id (e.g. `coach start english-coach`) or --all to run them all."
        )
        raise typer.Exit(code=0)

    if agent and not all_agents:
        target_dir = PROJECT_ROOT / "agents" / agent
        if not target_dir.exists():
            console.print(f"[red]no such agent:[/] {agent}")
            raise typer.Exit(code=1)
        env["COACH_ONLY_AGENT"] = agent
        console.print(f"[green]starting[/] {agent}")

    if all_agents:
        env.pop("COACH_ONLY_AGENT", None)
        console.print("[green]starting all agents[/]")

    proc = subprocess.run(
        [sys.executable, "-m", "runtime"],
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    raise typer.Exit(code=proc.returncode)
