"""Print active + disabled/completed tasks from HEARTBEAT.md and CRON.md.

Usage:
    python -m coach_agents.scripts.list_tasks --agent english-coach
    python -m coach_agents.scripts.list_tasks --agent english-coach --json
"""
from __future__ import annotations

import argparse
import json
import sys

from ._common import agent_dir, split_sections


def collect(agent_id: str) -> dict:
    adir = agent_dir(agent_id)
    out: dict[str, dict[str, list[str]]] = {"heartbeat": {}, "cron": {}}

    hb_path = adir / "HEARTBEAT.md"
    if hb_path.exists():
        sections = split_sections(hb_path.read_text(encoding="utf-8"))
        out["heartbeat"] = {
            "active": [ln.strip() for ln in sections.get("Active tasks", []) if ln.strip()],
            "completed": [ln.strip() for ln in sections.get("Completed", []) if ln.strip()],
        }

    cron_path = adir / "CRON.md"
    if cron_path.exists():
        sections = split_sections(cron_path.read_text(encoding="utf-8"))
        out["cron"] = {
            "active": [ln.strip() for ln in sections.get("Active", []) if ln.strip()],
            "disabled": [ln.strip() for ln in sections.get("Disabled", []) if ln.strip()],
        }

    return out


def render_markdown(agent_id: str, data: dict) -> str:
    lines: list[str] = [f"# Scheduled tasks for {agent_id}", ""]
    hb = data.get("heartbeat", {})
    lines.append("## Heartbeat (periodic)")
    active = hb.get("active", [])
    lines.append("**Active:**")
    lines.extend(active or ["- (none)"])
    completed = hb.get("completed", [])
    if completed:
        lines.append("")
        lines.append("**Completed:**")
        lines.extend(completed)
    lines.append("")
    lines.append("## Cron (calendar)")
    cron = data.get("cron", {})
    lines.append("**Active:**")
    lines.extend(cron.get("active", []) or ["- (none)"])
    disabled = cron.get("disabled", [])
    if disabled:
        lines.append("")
        lines.append("**Disabled:**")
        lines.extend(disabled)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = parser.parse_args()

    try:
        data = collect(args.agent)
    except FileNotFoundError as e:
        print(json.dumps({"ok": False, "reason": str(e)}))
        return 1

    if args.json:
        print(json.dumps({"ok": True, **data}, indent=2))
    else:
        print(render_markdown(args.agent, data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
