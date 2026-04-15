"""Smoke test: the fixture agent loads and validates."""

from __future__ import annotations

from pathlib import Path

from runtime.loader import load_agent


FIXTURE = Path(__file__).parent / "fixtures" / "sample-agent"


def test_fixture_agent_loads() -> None:
    loaded = load_agent(FIXTURE)
    assert loaded.agent_id == "sample-agent"
    assert "kb-research" in loaded.skills
    assert loaded.config["brain"]["type"] == "claude-code"
