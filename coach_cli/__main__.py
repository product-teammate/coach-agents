"""`coach <command>` — Typer app wiring all subcommands."""

from __future__ import annotations

import typer

from coach_cli.commands import (
    add_skill as add_skill_cmd,
    chat as chat_cmd,
    doctor as doctor_cmd,
    eval_cmd,
    learn as learn_cmd,
    new as new_cmd,
    start as start_cmd,
    status as status_cmd,
    stop as stop_cmd,
    trace as trace_cmd,
    validate as validate_cmd,
)

app = typer.Typer(
    help="Orchestrate personal coaching AI agents (Claude Code + Telegram, Phase 1)."
)

app.command("new")(new_cmd.new)
app.command("add-skill")(add_skill_cmd.add_skill)
app.command("start")(start_cmd.start)
app.command("stop")(stop_cmd.stop)
app.command("status")(status_cmd.status)
app.command("doctor")(doctor_cmd.doctor)
app.command("validate")(validate_cmd.validate)
app.command("learn")(learn_cmd.learn)
app.command("chat")(chat_cmd.chat)
app.add_typer(trace_cmd.trace_app, name="trace")
app.add_typer(eval_cmd.eval_app, name="eval")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
