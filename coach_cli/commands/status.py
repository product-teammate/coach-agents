"""`coach status` — list configured agents and their health signals."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from runtime.loader import discover_agents


console = Console()


def status() -> None:
    """Print a table of agents on disk, their enabled channels, and a last-msg hint."""
    table = Table(title="agents")
    table.add_column("id")
    table.add_column("name")
    table.add_column("channels")
    table.add_column("skills")
    table.add_column("last session")

    for loaded in discover_agents():
        channels = ",".join(
            c["type"] for c in loaded.config.get("channels", []) if c.get("enabled")
        ) or "-"
        skills = ",".join(loaded.skills) or "-"
        sessions = sorted(
            (loaded.directory / ".runtime" / "sessions").glob("*.json")
        ) if (loaded.directory / ".runtime" / "sessions").exists() else []
        last = "-"
        if sessions:
            newest = max(sessions, key=lambda p: p.stat().st_mtime)
            last = Path(newest).name
        table.add_row(loaded.agent_id, loaded.config["agent"]["name"], channels, skills, last)

    console.print(table)
    raise typer.Exit(code=0)
