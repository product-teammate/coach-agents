"""Smoke test: `coach --help` exits 0."""

from __future__ import annotations

from typer.testing import CliRunner

from coach_cli.__main__ import app


def test_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "coach" in result.output.lower() or "commands" in result.output.lower()
