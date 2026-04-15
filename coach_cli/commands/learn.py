"""``coach learn <id>`` — pre-load an agent's knowledge base.

Four modes, selected by argument pattern:

* ``coach learn <id>`` - AUTO: Claude plans topics from SOUL+USER.
* ``coach learn <id> "<topic>"`` - TARGETED: one topic.
* ``coach learn <id> --from urls.txt`` - BATCH: URL list.
* ``coach learn <id> --dry-run`` - AUTO plan only, no fetches.

The heavy lifting lives in ``coach_cli.learn_core`` so the heartbeat
consumer can reuse the exact same prompt + invocation path.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from coach_cli.learn_core import (
    LearnRequest,
    finalize_learn,
    format_file_summary,
    list_knowledge_files,
    parse_batch_file,
    stream_learn,
)


console = Console()


def learn(
    agent_id: str = typer.Argument(..., help="Agent id (folder under agents/)."),
    topic: str | None = typer.Argument(
        None,
        help="Optional topic for TARGETED mode. Omit for AUTO mode.",
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from",
        help="Path to a file of URLs (one per line) for BATCH mode.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="AUTO plan only, no fetches."
    ),
    max_files: int | None = typer.Option(
        None,
        "--max",
        help="Cap the number of files fetched this run (useful for testing).",
    ),
) -> None:
    """Pre-load the agent's ``knowledge/`` directory via Claude Code."""
    mode, urls = _resolve_mode(topic, from_file, dry_run)
    req = LearnRequest(
        agent_id=agent_id,
        mode=mode,
        topic=topic if mode == "targeted" else None,
        urls=urls,
        max_files=max_files,
    )
    try:
        asyncio.run(_run(req))
    except FileNotFoundError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1) from exc


def _resolve_mode(
    topic: str | None,
    from_file: Path | None,
    dry_run: bool,
) -> tuple[str, list[str] | None]:
    if from_file is not None:
        if topic:
            raise typer.BadParameter("cannot combine --from with a topic argument")
        if not from_file.exists():
            raise typer.BadParameter(f"batch file not found: {from_file}")
        urls = parse_batch_file(from_file)
        if not urls:
            raise typer.BadParameter(f"batch file is empty: {from_file}")
        return "batch", urls
    if dry_run:
        if topic:
            raise typer.BadParameter("--dry-run is only valid for AUTO mode")
        return "dry_run", None
    if topic:
        return "targeted", None
    return "auto", None


async def _run(req: LearnRequest) -> None:
    mode_label = {
        "auto": "AUTO",
        "dry_run": "DRY-RUN",
        "targeted": "TARGETED",
        "batch": "BATCH",
    }[req.mode]
    console.print(
        f"[bold]coach learn[/] {req.agent_id}  [dim]({mode_label})[/]"
    )
    buffer: list[str] = []
    async for chunk in stream_learn(req):
        buffer.append(chunk)
        # Stream to stdout so the operator sees progress live.
        console.print(chunk, end="", highlight=False, soft_wrap=True)
    console.print()  # trailing newline after stream

    if req.mode == "dry_run":
        console.print("[dim]dry-run complete - no files written.[/]")
        return

    index_path = finalize_learn(req.agent_id)
    if index_path is not None:
        console.print(f"[green]index:[/] {index_path}")
    files = list_knowledge_files(req.agent_id)
    console.print("[bold]knowledge files:[/]")
    console.print(format_file_summary(files))
