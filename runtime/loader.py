"""Load agents from disk: read agent.yaml, validate, hydrate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent.schema.json"


@dataclass(frozen=True)
class LoadedAgent:
    """Validated agent config + absolute paths."""

    agent_id: str
    directory: Path
    config: dict
    skills: list[str] = field(default_factory=list)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_agent(agent_dir: Path) -> LoadedAgent:
    """Load and validate a single agent directory."""
    config_path = agent_dir / "agent.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"missing agent.yaml in {agent_dir}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    validator = Draft202012Validator(_load_schema())
    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors)
        raise ValueError(f"invalid agent.yaml in {agent_dir}: {details}")

    soul_rel = config["persona"].get("soul", "SOUL.md")
    soul_path = agent_dir / soul_rel
    if not soul_path.exists() or not soul_path.read_text(encoding="utf-8").strip():
        raise ValueError(f"{soul_path} is empty or missing; describe the coach's persona first")

    skills = list(config.get("skills") or [])
    for name in skills:
        if not (PROJECT_ROOT / "skills" / name / "SKILL.md").exists():
            raise ValueError(f"agent references unknown skill: {name}")

    return LoadedAgent(
        agent_id=config["agent"]["id"],
        directory=agent_dir.resolve(),
        config=config,
        skills=skills,
    )


def discover_agents(agents_root: Path | None = None) -> list[LoadedAgent]:
    """Load every agents/<id>/ directory that contains agent.yaml."""
    root = (agents_root or (PROJECT_ROOT / "agents")).resolve()
    out: list[LoadedAgent] = []
    if not root.exists():
        return out
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "agent.yaml").exists():
            out.append(load_agent(child))
    return out
