# coach-agents

Orchestrate a fleet of personal coaching AI agents. Each agent specializes in
one learning domain (English, Playwright, Math, ...) and is composed of three
swappable layers:

1. **Brain** — the LLM runtime that plans and acts. Phase 1 uses the
   [Claude Code CLI](https://docs.claude.com/claude-code) as a subprocess.
2. **Channel** — where the learner actually talks to the agent. Phase 1
   ships Telegram (long-polling) and Slack (Socket Mode) adapters, plus
   a stdin/stdout CLI channel for local dev. Discord is Phase 2.
3. **Skills** — shared, file-based capabilities discovered by the brain. All
   agents draw from the same `skills/` library (RAG research, quiz making,
   flashcards, memory ops, heartbeat reminders, feedback loop, ...).

Each agent lives in `agents/<id>/` as an editable folder: `agent.yaml`,
`SOUL.md` (persona), `USER.md` (learner profile), `MEMORY.md`,
`HEARTBEAT.md`, and a `knowledge/` directory. The runtime composes a
fresh `CLAUDE.md` per turn so the brain sees exactly the right context.

## Architecture

```
                 +---------------------+
  Telegram  -->  |     channels/      |
  (future: Slack,|   adapters + UI   |
   Discord, CLI) +----------+----------+
                            |
                            v
                 +----------+----------+
                 |     runtime/       |  loader, router, queue,
                 |  per-user queue    |  scheduler, permissions
                 +----------+----------+
                            |
                            v
                 +----------+----------+
                 |      brains/       |  claude-code (P1)
                 |  claude-code subp. |  codex / antigravity (stub)
                 +----------+----------+
                            |
                            v
                 +----------+----------+
                 |     agents/<id>/   |  SOUL / USER / MEMORY /
                 |  per-agent state   |  HEARTBEAT / knowledge/
                 +----------+----------+
                            |
                            v
                 +----------+----------+
                 |      skills/       |  shared library referenced
                 |  SKILL.md manifests|  from each agent.yaml
                 +---------------------+
```

## Quick start

Two live coaches ship in `agents/`:

- **`english-coach`** — Ava, English A2 -> C1 (Slack)
- **`playwright-coach`** — Rook, first spec -> 500-test CI pipeline (Slack)

```bash
git clone https://github.com/product-teammate/coach-agents.git
cd coach-agents
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Sanity check your environment.
coach doctor

# Copy tokens. For the two pre-built coaches, set:
#   SLACK_ENGLISH_BOT_TOKEN=xoxb-...
#   SLACK_ENGLISH_APP_TOKEN=xapp-...
#   SLACK_PLAYWRIGHT_BOT_TOKEN=xoxb-...
#   SLACK_PLAYWRIGHT_APP_TOKEN=xapp-...
cp .env.example .env
$EDITOR .env

# Validate and run.
coach validate english-coach
coach validate playwright-coach
coach start --all          # or: coach start english-coach
```

Scaffold your own coach from scratch:

```bash
coach new my-coach                 # prompts for channel + optional knowledge pre-load
# edit agents/my-coach/SOUL.md
coach learn my-coach               # AUTO: plan topics from SOUL and ingest authoritative sources
coach validate my-coach
coach start my-coach               # filters to one agent via COACH_ONLY_AGENT
```

Knowledge ingestion has four modes (see
[docs/knowledge-management.md](docs/knowledge-management.md)):

```bash
coach learn my-coach                        # AUTO - plan + fetch
coach learn my-coach "conditionals"         # TARGETED - one topic
coach learn my-coach --from urls.txt        # BATCH - explicit URL list
coach learn my-coach --dry-run              # AUTO plan only, no writes
```

Iterate without the `claude` CLI logged in:

```bash
COACH_BRAIN_STUB=1 coach start --all
```

## Docs

- [docs/architecture.md](docs/architecture.md) — module map and data flow
- [docs/new-agent-walkthrough.md](docs/new-agent-walkthrough.md) — step-by-step
- [docs/knowledge-management.md](docs/knowledge-management.md) — `coach learn`, sources, onboarding flow
- [docs/brain-interface.md](docs/brain-interface.md) — Brain Protocol contract
- [docs/channel-interface.md](docs/channel-interface.md) — Channel Protocol
- [docs/skill-authoring.md](docs/skill-authoring.md) — how to write a SKILL.md
- [docs/permissions.md](docs/permissions.md) — tool whitelist merge logic
- [docs/security.md](docs/security.md) — tokens, gists, logs
- [docs/phase-2-roadmap.md](docs/phase-2-roadmap.md) — what is next

## Roadmap

- **Phase 1** (current): Claude Code brain + Telegram + Slack channels,
  heartbeat scheduler, gist-based quiz/flashcard publishing, two live
  coaches (Ava, Rook).
- **Phase 2**: Discord adapter, codex + antigravity brains, local RAG
  via Ollama, persistent scheduler JobStore. See
  [docs/phase-2-roadmap.md](docs/phase-2-roadmap.md).

## License

MIT — see [LICENSE](LICENSE).
