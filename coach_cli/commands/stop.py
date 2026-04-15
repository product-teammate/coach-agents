"""`coach stop` — placeholder; Phase 1 expects Ctrl-C in the start session."""

from __future__ import annotations

import typer
from rich.console import Console


console = Console()


def stop(
    agent: str = typer.Argument(None, help="Agent id to stop."),
) -> None:
    """Phase 1 stub — send SIGINT to the runtime process yourself.

    A real implementation will maintain a PID file per agent and send the
    signal on your behalf.
    """
    console.print(
        "[yellow]stop is a stub in Phase 1.[/] "
        "Send SIGINT (Ctrl-C) to the runtime process."
    )
    if agent:
        console.print(f"requested agent: {agent}")
    raise typer.Exit(code=0)
