# Phase 2 roadmap

Phase 1 ships Claude Code + Telegram. Phase 2 focuses on breadth.

## Brains

- **codex** — wrap the OpenAI Codex CLI with the same subprocess model.
- **antigravity** — placeholder for Google Antigravity.

Both should share a small subprocess-brain base class with `claude_code`
(command builder, stream parser, session management).

## Channels

- **slack** — port DeepTutor's Slack integration.
- **discord** — add a `discord.py`-based adapter with slash commands.
- Upgrade **cli** to a Rich TUI for local dev.

## Skills library

- Flesh out working scripts for `quiz-maker`, `flashcard-deck`, and
  `memory-ops` (right now only `kb-research` has scripts).
- Build a skill test harness: each skill ships a small suite the runtime
  can run in stub mode.

## Knowledge

- Phase 4: swap file-read mode for a local Ollama-backed RAG index.
  `knowledge/` stays canonical; an index is rebuilt on ingest.

## Runtime

- PID files for `coach stop` to actually send signals.
- Persistent APScheduler JobStore per agent.
- Health endpoint for `coach status --live`.
