"""Shared helpers for coach_agents.scripts.* operator tools."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = PROJECT_ROOT / "agents"

HEARTBEAT_TEMPLATE = """# Heartbeat Tasks

*This file is checked every `interval_s` seconds (see agent.yaml `proactive.heartbeat.interval_s`).*
*Add tasks the coach should work on periodically. Empty = no proactive messages.*

## Active tasks

## Completed
"""

CRON_TEMPLATE = """# Cron Jobs

*Calendar-scheduled jobs parsed by the runtime (see docs/scheduling.md).*

## Active

## Disabled
"""


def agent_dir(agent_id: str) -> Path:
    """Return the absolute path to ``agents/<id>``; raise if missing."""
    path = AGENTS_ROOT / agent_id
    if not path.exists():
        raise FileNotFoundError(f"agent_not_found: {agent_id}")
    return path


def ensure_heartbeat_file(agent_id: str) -> Path:
    path = agent_dir(agent_id) / "HEARTBEAT.md"
    if not path.exists():
        path.write_text(HEARTBEAT_TEMPLATE, encoding="utf-8")
    return path


def ensure_cron_file(agent_id: str) -> Path:
    path = agent_dir(agent_id) / "CRON.md"
    if not path.exists():
        path.write_text(CRON_TEMPLATE, encoding="utf-8")
    return path


def split_sections(text: str) -> dict[str, list[str]]:
    """Split markdown by `## ` headers into section_name -> body lines."""
    sections: dict[str, list[str]] = {"__preamble__": []}
    current = "__preamble__"
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def render_sections(order: list[str], sections: dict[str, list[str]]) -> str:
    """Re-render section dict back to markdown, preserving order."""
    parts: list[str] = []
    preamble = sections.get("__preamble__", [])
    if preamble:
        parts.append("\n".join(preamble).rstrip() + "\n")
    for name in order:
        if name == "__preamble__":
            continue
        body = sections.get(name, [])
        parts.append(f"## {name}")
        body_text = "\n".join(body).strip("\n")
        if body_text:
            parts.append(body_text)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
