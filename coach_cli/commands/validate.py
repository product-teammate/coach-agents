"""`coach validate <agent_id>` — schema-check and sanity-check an agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from runtime.loader import PROJECT_ROOT, load_agent


console = Console()


def validate(
    agent: str = typer.Argument(..., help="Agent id OR path to an agent directory."),
) -> None:
    """Validate agent.yaml against the schema and verify skills resolve."""
    candidate = Path(agent)
    if candidate.exists() and candidate.is_dir():
        agent_dir = candidate.resolve()
    else:
        agent_dir = PROJECT_ROOT / "agents" / agent
    if not agent_dir.exists():
        console.print(f"[red]no such agent:[/] {agent}")
        raise typer.Exit(code=1)

    try:
        loaded = load_agent(agent_dir)
    except Exception as exc:  # noqa: BLE001 — surface full error to the user
        console.print(f"[red]invalid:[/] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]ok[/] {loaded.agent_id} at {loaded.directory}")
    console.print(f"  skills: {', '.join(loaded.skills) or '(none)'}")
    channels = [c["type"] for c in loaded.config.get("channels", []) if c.get("enabled")]
    console.print(f"  channels: {', '.join(channels) or '(none enabled)'}")
