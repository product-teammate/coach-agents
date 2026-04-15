"""Deactivate a recurring task by matching substring across HEARTBEAT.md + CRON.md.

Moves matched lines from Active -> Completed (heartbeat) or Active -> Disabled (cron).
Adds a trailing `(disabled <ISO>)` marker to the moved line.

Usage:
    python -m coach_agents.scripts.remove_task --agent english-coach --match "phrasal verb"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from ._common import agent_dir, render_sections, split_sections


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _move_matching(
    path: Path,
    active_section: str,
    target_section: str,
    section_order: list[str],
    match: str,
) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)
    active = sections.get(active_section, [])
    target_body = sections.setdefault(target_section, [])

    needle = match.lower()
    moved: list[str] = []
    remaining: list[str] = []
    for raw in active:
        stripped = raw.strip()
        if stripped and needle in stripped.lower():
            marker = f" (disabled {_now_iso()})"
            target_body.append(raw.rstrip() + marker)
            moved.append(raw.strip())
        else:
            remaining.append(raw)

    if moved:
        sections[active_section] = remaining
        path.write_text(render_sections(section_order, sections), encoding="utf-8")
    return moved


def remove(agent_id: str, match: str) -> dict:
    adir = agent_dir(agent_id)
    hb_moved = _move_matching(
        adir / "HEARTBEAT.md",
        active_section="Active tasks",
        target_section="Completed",
        section_order=["Active tasks", "Completed"],
        match=match,
    )
    cron_moved = _move_matching(
        adir / "CRON.md",
        active_section="Active",
        target_section="Disabled",
        section_order=["Active", "Disabled"],
        match=match,
    )
    return {
        "ok": bool(hb_moved or cron_moved),
        "heartbeat_removed": hb_moved,
        "cron_removed": cron_moved,
        "reason": "removed" if (hb_moved or cron_moved) else "no_match",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--match", required=True, help="case-insensitive substring")
    args = parser.parse_args()

    try:
        result = remove(args.agent, args.match)
    except FileNotFoundError as e:
        print(json.dumps({"ok": False, "reason": str(e)}))
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
