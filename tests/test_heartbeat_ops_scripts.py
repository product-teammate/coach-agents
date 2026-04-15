"""Tests for the coach_agents.scripts.* operator tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from coach_agents.scripts import add_task, check_channel, list_tasks, remove_task
from coach_agents.scripts import _common


@pytest.fixture
def isolated_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Build a fake agents/<id> directory and redirect AGENTS_ROOT to it."""
    agent_id = "test-agent"
    adir = tmp_path / "agents" / agent_id
    adir.mkdir(parents=True)
    (adir / "agent.yaml").write_text(
        yaml.safe_dump(
            {
                "agent": {"id": agent_id, "name": "T", "version": "0.1.0"},
                "channels": [
                    {"type": "slack", "enabled": True, "env_prefix": "SLK_TEST_"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(_common, "AGENTS_ROOT", tmp_path / "agents")
    return agent_id


class _FakeResp(dict):
    """dict subclass that mimics slack_sdk's AsyncSlackResponse.__getitem__."""


def _make_client(auth_user: str = "U-BOT", channels=None, members=None) -> MagicMock:
    client = MagicMock()
    client.auth_test = AsyncMock(return_value=_FakeResp({"user_id": auth_user}))
    client.conversations_list = AsyncMock(
        return_value=_FakeResp(
            {"channels": channels or [], "response_metadata": {"next_cursor": ""}}
        )
    )
    client.conversations_members = AsyncMock(
        return_value=_FakeResp(
            {"members": members or [], "response_metadata": {"next_cursor": ""}}
        )
    )
    return client


@pytest.mark.asyncio
async def test_check_channel_dm_always_ok(
    isolated_agent: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLK_TEST_BOT_TOKEN", "xoxb-fake")
    fake_client = _make_client()
    with patch(
        "slack_sdk.web.async_client.AsyncWebClient", return_value=fake_client
    ):
        result = await check_channel.check(isolated_agent, "dm")
    assert result["ok"] is True
    assert result["reason"] == "always_ok"


@pytest.mark.asyncio
async def test_check_channel_member(
    isolated_agent: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLK_TEST_BOT_TOKEN", "xoxb-fake")
    fake_client = _make_client(
        channels=[{"id": "C1", "name": "general"}],
        members=["U-BOT", "U-OTHER"],
    )
    with patch(
        "slack_sdk.web.async_client.AsyncWebClient", return_value=fake_client
    ):
        result = await check_channel.check(isolated_agent, "channel:general")
    assert result["ok"] is True
    assert result["reason"] == "member"
    assert result["channel_id"] == "C1"


@pytest.mark.asyncio
async def test_check_channel_not_in_channel(
    isolated_agent: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLK_TEST_BOT_TOKEN", "xoxb-fake")
    fake_client = _make_client(
        channels=[{"id": "C2", "name": "private-room"}],
        members=["U-OTHER"],
    )
    with patch(
        "slack_sdk.web.async_client.AsyncWebClient", return_value=fake_client
    ):
        result = await check_channel.check(isolated_agent, "channel:private-room")
    assert result["ok"] is False
    assert result["reason"] == "not_in_channel"
    assert result["channel_id"] == "C2"


@pytest.mark.asyncio
async def test_check_channel_not_found(
    isolated_agent: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLK_TEST_BOT_TOKEN", "xoxb-fake")
    fake_client = _make_client(channels=[{"id": "C3", "name": "other"}])
    with patch(
        "slack_sdk.web.async_client.AsyncWebClient", return_value=fake_client
    ):
        result = await check_channel.check(isolated_agent, "channel:does-not-exist")
    assert result["ok"] is False
    assert result["reason"] == "channel_not_found"


@pytest.mark.asyncio
async def test_check_channel_missing_token(isolated_agent: str) -> None:
    os.environ.pop("SLK_TEST_BOT_TOKEN", None)
    result = await check_channel.check(isolated_agent, "dm")
    assert result["ok"] is False
    assert result["reason"] == "missing_bot_token"


def test_add_task_heartbeat_happy_path(isolated_agent: str) -> None:
    result = add_task.add_heartbeat(
        isolated_agent, "every 2h", "Send 1 phrasal verb", "D123"
    )
    assert result["ok"] is True
    assert result["added"] is True

    path = _common.agent_dir(isolated_agent) / "HEARTBEAT.md"
    body = path.read_text(encoding="utf-8")
    assert "[every 2h]" in body
    assert "Send 1 phrasal verb" in body
    assert "target: D123" in body
    assert "## Active tasks" in body
    assert "## Completed" in body


def test_add_task_dedupe(isolated_agent: str) -> None:
    add_task.add_heartbeat(isolated_agent, "every 2h", "Daily drill", "D123")
    second = add_task.add_heartbeat(
        isolated_agent, "every 2h", "Daily drill", "D123"
    )
    assert second["ok"] is True
    assert second["added"] is False
    assert second["reason"] == "duplicate"


def test_add_task_cron_happy_path(isolated_agent: str) -> None:
    result = add_task.add_cron(
        isolated_agent, "0 8 * * *", "Morning drill", "D123"
    )
    assert result["ok"] is True, result
    body = (_common.agent_dir(isolated_agent) / "CRON.md").read_text(
        encoding="utf-8"
    )
    assert "[0 8 * * *]" in body
    assert "Morning drill" in body


def test_add_task_cron_invalid(isolated_agent: str) -> None:
    result = add_task.add_cron(
        isolated_agent, "not a cron", "Anything", "D123"
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_cron_expression"


def test_remove_task_moves_line_to_completed(isolated_agent: str) -> None:
    add_task.add_heartbeat(
        isolated_agent, "every 2h", "Send 1 phrasal verb", "D123"
    )
    result = remove_task.remove(isolated_agent, "phrasal verb")
    assert result["ok"] is True
    assert len(result["heartbeat_removed"]) == 1

    body = (_common.agent_dir(isolated_agent) / "HEARTBEAT.md").read_text(
        encoding="utf-8"
    )
    # Active tasks section should be empty, Completed should contain the line.
    sections = _common.split_sections(body)
    assert not any(ln.strip() for ln in sections["Active tasks"])
    completed_text = "\n".join(sections["Completed"])
    assert "phrasal verb" in completed_text
    assert "(disabled " in completed_text


def test_remove_task_no_match(isolated_agent: str) -> None:
    result = remove_task.remove(isolated_agent, "nothing-here")
    assert result["ok"] is False
    assert result["reason"] == "no_match"


def test_list_tasks_reports_contents(isolated_agent: str) -> None:
    add_task.add_heartbeat(isolated_agent, "every 2h", "Task A", "D1")
    add_task.add_cron(isolated_agent, "0 8 * * *", "Task B", "D2")
    data = list_tasks.collect(isolated_agent)
    assert any("Task A" in ln for ln in data["heartbeat"]["active"])
    assert any("Task B" in ln for ln in data["cron"]["active"])

    md = list_tasks.render_markdown(isolated_agent, data)
    assert "Heartbeat" in md
    assert "Cron" in md
    assert "Task A" in md and "Task B" in md


def test_check_channel_cli_exit_code(
    isolated_agent: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Exit code is 0 on ok, 1 otherwise; always emits JSON."""
    monkeypatch.setenv("SLK_TEST_BOT_TOKEN", "xoxb-fake")
    fake_client = _make_client()
    with patch("sys.argv", ["check_channel", "--agent", isolated_agent, "--target", "dm"]):
        with patch(
            "slack_sdk.web.async_client.AsyncWebClient", return_value=fake_client
        ):
            code = check_channel.main()
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["ok"] is True
