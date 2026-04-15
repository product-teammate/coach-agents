"""Private helper: regenerate ``knowledge/INDEX.md`` for an agent.

Scans every ``*.md`` file in the agent's knowledge directory (excluding
``INDEX.md`` itself and anything under ``_summaries/``), extracts the
``topic`` and ``source`` fields from the YAML frontmatter, and writes a
single sorted index file.

Kept dependency-free — the frontmatter parser is a few lines of string
matching, mirroring ``runtime.permissions.read_skill_tools``.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _summary_line(path: Path) -> str:
    """Return a one-line summary for a knowledge file.

    Preference order: frontmatter ``topic`` field, then the first Markdown
    heading, then the filename stem.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return path.stem
    fm = _parse_frontmatter(text)
    topic = fm.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()
    # Strip frontmatter before searching for the first heading.
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4 :]
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip() or path.stem
    return path.stem


def regenerate_index(knowledge_dir: Path) -> Path:
    """Write ``knowledge_dir/INDEX.md`` sorted alphabetically by filename.

    Returns the path to the written INDEX.md. If the directory does not
    exist or contains no knowledge files, an INDEX.md with a stub body is
    still written (so later reads don't have to special-case absence).
    """
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str]] = []
    for child in sorted(knowledge_dir.iterdir()):
        if not child.is_file() or child.suffix != ".md":
            continue
        if child.name == "INDEX.md":
            continue
        entries.append((child.name, _summary_line(child)))

    lines = ["# Knowledge Index", ""]
    if not entries:
        lines.append("*No knowledge files yet. Run `coach learn <id>` to populate.*")
    else:
        for name, summary in entries:
            lines.append(f"- `{name}` - {summary}")
    lines.append("")

    out = knowledge_dir / "INDEX.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
