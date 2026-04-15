"""`coach add-skill <agent_id> <skill>` — append a skill to an agent.yaml."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console


PROJECT_ROOT = Path(__file__).resolve().parents[2]
console = Console()


def add_skill(
    agent_id: str = typer.Argument(...),
    skill: str = typer.Argument(..., help="Skill name, e.g. kb-research"),
) -> None:
    """Append a skill name to agents/<id>/agent.yaml (idempotent)."""
    agent_dir = PROJECT_ROOT / "agents" / agent_id
    config_path = agent_dir / "agent.yaml"
    if not config_path.exists():
        raise typer.BadParameter(f"no such agent: {agent_id}")
    if not (PROJECT_ROOT / "skills" / skill / "SKILL.md").exists():
        raise typer.BadParameter(f"no such skill: {skill}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    skills = list(config.get("skills") or [])
    if skill in skills:
        console.print(f"[yellow]{skill} already enabled[/] for {agent_id}")
        return
    skills.append(skill)
    config["skills"] = skills
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    console.print(f"[green]added[/] {skill} to {agent_id}")
