# Phase 2 roadmap

Phase 1 ships Claude Code brain + Telegram + Slack channels, the core
skill library, a working heartbeat scheduler, and two live coaches (Ava,
Rook). Phase 2 focuses on breadth and durability.

## Brains

- **codex** — wrap the OpenAI Codex CLI with the same subprocess model.
- **antigravity** — placeholder for Google Antigravity.

Both should share a small subprocess-brain base class with `claude_code`
(command builder, stream parser, session management).

## Channels

- **discord** — add a `discord.py`-based adapter with slash commands.
- Upgrade **cli** to a Rich TUI for local dev.

## Skills library

- Flesh out working scripts for `memory-ops` and `conversation-recap`.
- Build a skill test harness: each skill ships a small suite the runtime
  can run in stub mode.
- Cron job registration API exposed to skills. Today the scheduler only
  runs the heartbeat loop; skills cannot register their own cron jobs
  from within a turn (the runtime logs a warning when
  `proactive.cron.enabled: true`). Unblocks `cron-ops`.

## Knowledge

- Swap file-read mode for a local Ollama-backed RAG index. `knowledge/`
  stays canonical; an index is rebuilt on ingest.

## Runtime

- PID files for `coach stop` to actually send signals.
- Persistent APScheduler JobStore per agent (today it's in-memory only,
  so heartbeats are lost across restarts).
- Health endpoint for `coach status --live`.
