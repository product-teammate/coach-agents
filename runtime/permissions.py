"""Merge agent-level + skill-level tool whitelists into a final allowed list.

Why: agents declare a baseline of tools they trust; each skill declares the
tools IT needs. The brain invocation uses the union, deduplicated, stable-
ordered. Skills cannot escalate beyond the explicit union; if a skill wants
a tool the agent refuses, the agent wins.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_skill_tools(skill_name: str) -> list[str]:
    """Read `required_tools` from a skill's SKILL.md frontmatter."""
    manifest = PROJECT_ROOT / "skills" / skill_name / "SKILL.md"
    if not manifest.exists():
        return []
    raw = manifest.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return []
    end = raw.find("---", 3)
    if end == -1:
        return []
    frontmatter = yaml.safe_load(raw[3:end]) or {}
    tools = frontmatter.get("required_tools") or []
    return [str(t) for t in tools]


def merge_tools(agent_tools: Iterable[str], skills: Iterable[str]) -> list[str]:
    """Return the final allowed-tools list for a brain invocation."""
    seen: dict[str, None] = {}
    for tool in agent_tools:
        seen.setdefault(tool, None)
    for skill in skills:
        for tool in read_skill_tools(skill):
            seen.setdefault(tool, None)
    return list(seen.keys())
