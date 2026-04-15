"""Append a recurring task to HEARTBEAT.md (periodic) or CRON.md (calendar).

Usage:
    python -m coach_agents.scripts.add_task \\
        --agent english-coach --mode heartbeat \\
        --schedule "every 2h" --task "Send 1 phrasal verb" --target D123ABC

    python -m coach_agents.scripts.add_task \\
        --agent english-coach --mode cron \\
        --schedule "0 8 * * *" --task "Morning drill" --target C456DEF

De-duplicates identical lines. Validates cron expressions via croniter.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys

from ._common import (
    ensure_cron_file,
    ensure_heartbeat_file,
    render_sections,
    split_sections,
)


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _format_line(schedule: str, task: str, target: str, now: str) -> str:
    return f"- [{schedule}] {task} \u2192 target: {target} (added {now})"


def _insert(
    path,
    section: str,
    line: str,
    section_order: list[str],
) -> dict:
    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)
    section_body = sections.setdefault(section, [])
    # Dedupe on schedule+task+target (ignore "added" timestamp suffix).
    core = line.split(" (added ", 1)[0]
    for existing in section_body:
        if existing.strip().startswith(core):
            return {"ok": True, "added": False, "reason": "duplicate", "line": existing.strip()}
    # Normalise: if section is empty (only blanks), reset it.
    if all(not ln.strip() for ln in section_body):
        sections[section] = [line]
    else:
        # Strip trailing blanks, append, preserve one trailing newline.
        while section_body and not section_body[-1].strip():
            section_body.pop()
        section_body.append(line)
    path.write_text(render_sections(section_order, sections), encoding="utf-8")
    return {"ok": True, "added": True, "reason": "appended", "line": line}


def add_heartbeat(agent_id: str, schedule: str, task: str, target: str) -> dict:
    path = ensure_heartbeat_file(agent_id)
    line = _format_line(schedule, task, target, _now_iso())
    return _insert(path, "Active tasks", line, ["Active tasks", "Completed"])


def add_cron(agent_id: str, schedule: str, task: str, target: str) -> dict:
    # Validate cron expression.
    try:
        from croniter import croniter  # type: ignore
    except ImportError:  # pragma: no cover — croniter is a declared dep
        return {"ok": False, "reason": "croniter_not_installed"}
    if not croniter.is_valid(schedule):
        return {"ok": False, "reason": "invalid_cron_expression", "schedule": schedule}
    path = ensure_cron_file(agent_id)
    line = _format_line(schedule, task, target, _now_iso())
    return _insert(path, "Active", line, ["Active", "Disabled"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--mode", required=True, choices=["heartbeat", "cron"])
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    if args.mode == "heartbeat":
        result = add_heartbeat(args.agent, args.schedule, args.task, args.target)
    else:
        result = add_cron(args.agent, args.schedule, args.task, args.target)

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
