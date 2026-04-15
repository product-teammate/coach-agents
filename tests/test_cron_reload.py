"""Smoke tests for the CRON.md parser + reconcile loop."""
from __future__ import annotations

from pathlib import Path

from runtime.cron_loader import CronEntry, parse_cron_file, reconcile


def test_parse_cron_file(tmp_path: Path) -> None:
    path = tmp_path / "CRON.md"
    path.write_text(
        """# Cron Jobs

## Active

- [0 8 * * *] Morning drill \u2192 target: D123 (added 2026-04-16T08:00Z)
- [*/15 * * * *] Frequent check \u2192 target: C456 (added 2026-04-16T08:00Z)

## Disabled

- [0 20 * * *] Old task \u2192 target: D123 (disabled 2026-04-10T08:00Z)
""",
        encoding="utf-8",
    )
    entries = parse_cron_file(path)
    assert len(entries) == 2
    assert entries[0].cron_expr == "0 8 * * *"
    assert entries[0].task == "Morning drill"
    assert entries[0].target == "D123"
    assert entries[1].cron_expr == "*/15 * * * *"


def test_parse_cron_file_skips_disabled(tmp_path: Path) -> None:
    path = tmp_path / "CRON.md"
    path.write_text(
        "## Active\n\n## Disabled\n- [0 8 * * *] Old \u2192 target: D1\n",
        encoding="utf-8",
    )
    assert parse_cron_file(path) == []


def test_parse_cron_file_missing(tmp_path: Path) -> None:
    assert parse_cron_file(tmp_path / "nope.md") == []


def test_reconcile_adds_and_removes(tmp_path: Path) -> None:
    first = [CronEntry("0 8 * * *", "Task A", "D1")]
    second = [CronEntry("0 9 * * *", "Task B", "D2")]

    added_ids: list[str] = []
    removed_ids: list[str] = []
    registered: dict[str, CronEntry] = {}

    def _add(job_id: str, cron_expr: str, cb) -> None:  # type: ignore[no-untyped-def]
        added_ids.append(job_id)

    def _remove(job_id: str) -> None:
        removed_ids.append(job_id)

    def _make_cb(entry: CronEntry):  # type: ignore[no-untyped-def]
        async def _noop() -> None:
            return None

        return _noop

    added, removed = reconcile("a", first, registered, _add, _remove, _make_cb)
    assert added == 1
    assert removed == 0
    assert len(registered) == 1

    # Replace the set entirely.
    added, removed = reconcile("a", second, registered, _add, _remove, _make_cb)
    assert added == 1
    assert removed == 1
    assert list(registered.values())[0].task == "Task B"


def test_reconcile_noop_on_stable_input(tmp_path: Path) -> None:
    entries = [CronEntry("0 8 * * *", "Task A", "D1")]
    registered: dict[str, CronEntry] = {}
    calls = {"add": 0, "remove": 0}

    def _add(job_id: str, cron_expr: str, cb) -> None:  # type: ignore[no-untyped-def]
        calls["add"] += 1

    def _remove(job_id: str) -> None:
        calls["remove"] += 1

    def _make_cb(entry: CronEntry):  # type: ignore[no-untyped-def]
        async def _noop() -> None:
            return None

        return _noop

    reconcile("a", entries, registered, _add, _remove, _make_cb)
    reconcile("a", entries, registered, _add, _remove, _make_cb)
    assert calls == {"add": 1, "remove": 0}


def test_permissions_merge_picks_up_heartbeat_ops_v2() -> None:
    """Sanity: permissions.merge_tools must include Bash/Grep from the new SKILL.md."""
    from runtime.permissions import merge_tools

    merged = merge_tools([], ["heartbeat-ops"])
    for tool in ("Read", "Write", "Edit", "Bash", "Grep"):
        assert tool in merged, f"missing {tool} in merged tools: {merged}"
