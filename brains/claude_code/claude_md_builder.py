"""Generate a fresh CLAUDE.md per turn from SOUL.md + USER.md + skills list.

CLAUDE.md is the prompt the `claude` CLI consumes as system context. We
rebuild it from canonical inputs so user edits to SOUL.md flow through
immediately and stale prompts never drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


TEMPLATE = """# Agent runtime context

> Auto-generated — edit SOUL.md, USER.md, or agent.yaml instead.

## Persona (SOUL.md)

{soul}

## Learner profile (USER.md)

{user}

## Enabled skills

The following skills live under `skills/` at the project root. Consult
their `SKILL.md` before acting — every skill tells you when it applies
and how it expects to be used.

{skills_table}

## Operating rules

- Respect `.agentignore` when listing or reading files.
- Keep replies suited to the channel ({channel_hint}).
- Update MEMORY.md via the `memory-ops` skill, not by direct edit.
- If a skill is relevant, prefer its playbook over improvising.
"""


def _read_or_blank(path: Path) -> str:
    if not path.exists():
        return "_(not set)_"
    return path.read_text(encoding="utf-8").strip() or "_(empty)_"


def _skills_table(project_root: Path, skill_names: Iterable[str]) -> str:
    lines = []
    for name in skill_names:
        manifest = project_root / "skills" / name / "SKILL.md"
        if not manifest.exists():
            lines.append(f"- `{name}` — (missing manifest)")
            continue
        description = _extract_description(manifest)
        lines.append(f"- `{name}` — {description}")
    if not lines:
        lines.append("- _(none configured — add entries to agent.yaml.skills)_")
    return "\n".join(lines)


def _extract_description(manifest: Path) -> str:
    text = manifest.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    return ""


def build_claude_md(
    agent_dir: Path,
    project_root: Path,
    skills: Iterable[str],
    channel_hint: str = "telegram",
) -> str:
    """Render CLAUDE.md content without writing to disk."""
    soul = _read_or_blank(agent_dir / "SOUL.md")
    user = _read_or_blank(agent_dir / "USER.md")
    return TEMPLATE.format(
        soul=soul,
        user=user,
        skills_table=_skills_table(project_root, skills),
        channel_hint=channel_hint,
    )


def write_claude_md(
    agent_dir: Path,
    project_root: Path,
    skills: Iterable[str],
    channel_hint: str = "telegram",
) -> Path:
    """Write CLAUDE.md to the agent directory and return the path."""
    content = build_claude_md(agent_dir, project_root, skills, channel_hint)
    target = agent_dir / "CLAUDE.md"
    target.write_text(content, encoding="utf-8")
    return target
