"""`coach new <id>` — scaffold a new agent from template/."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import typer
import yaml
from rich.console import Console


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / "template"
AGENTS_DIR = PROJECT_ROOT / "agents"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

console = Console()


def new(
    agent_id: str = typer.Argument(..., help="kebab-case agent id, e.g. english-coach"),
    name: str = typer.Option(None, help="Display name. Prompted if omitted."),
    description: str = typer.Option(None, help="Short description. Prompted if omitted."),
    channel: str = typer.Option(
        "telegram",
        help="Channel to enable: telegram | cli",
        show_choices=True,
    ),
    viewer: str = typer.Option(
        "https://product-teammate.github.io/gist-render/viewer/",
        help="Viewer base URL for quiz / flashcard gists.",
    ),
) -> None:
    """Copy template/ to agents/<id>/ and patch agent.yaml."""
    if not _ID_RE.match(agent_id):
        raise typer.BadParameter(f"agent id must match {_ID_RE.pattern}")

    target = AGENTS_DIR / agent_id
    if target.exists():
        raise typer.BadParameter(f"{target} already exists")

    if name is None:
        name = typer.prompt("Display name", default=agent_id.replace("-", " ").title())
    if description is None:
        description = typer.prompt("One-line description", default="")

    shutil.copytree(TEMPLATE_DIR, target)

    config_path = target / "agent.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["agent"]["id"] = agent_id
    config["agent"]["name"] = name
    config["agent"]["description"] = description
    # Keep only the chosen channel enabled.
    new_channels = []
    if channel == "telegram":
        new_channels.append(
            {
                "type": "telegram",
                "enabled": True,
                "env_prefix": f"TELEGRAM_{agent_id.upper().replace('-', '_')}_",
                "allow_from": [],
                "mode": "polling",
            }
        )
    elif channel == "cli":
        new_channels.append({"type": "cli", "enabled": True})
    else:
        raise typer.BadParameter(f"unknown channel: {channel}")
    config["channels"] = new_channels
    config.setdefault("viewer", {})["renderer_base"] = viewer
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    console.print(f"[green]created[/] {target}")
    console.print("Next steps:")
    console.print(f"  1. Edit {target / 'SOUL.md'} with the coach persona.")
    console.print(f"  2. Fill in {target / 'USER.md'} with your learner profile.")
    console.print(f"  3. Export the channel env var(s) from .env.example.")
    console.print(f"  4. Run: coach validate {agent_id}")
