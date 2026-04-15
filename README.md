# coach-agents

Orchestrate a fleet of personal coaching AI agents. Each agent specializes in
one learning domain (English, Playwright, Math, ...) and is composed of three
swappable layers:

1. **Brain** — the LLM runtime that plans and acts. Phase 1 uses the
   [Claude Code CLI](https://docs.claude.com/claude-code) as a subprocess.
2. **Channel** — where the learner actually talks to the agent. Phase 1 ships
   a Telegram long-polling adapter; Slack/Discord/CLI are stubbed.
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

```bash
git clone https://github.com/product-teammate/coach-agents.git
cd coach-agents
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Sanity check your environment.
coach doctor

# Create your first agent.
coach new english-coach

# Edit agents/english-coach/SOUL.md, USER.md, and agent.yaml.
# Export the Telegram token per your env_prefix, e.g.:
export TELEGRAM_ENGLISH_BOT_TOKEN=...

# Validate and start it.
coach validate english-coach
coach start english-coach
```

You can run in stub mode without the `claude` CLI installed:

```bash
COACH_BRAIN_STUB=1 coach start english-coach
```

## Docs

- [docs/architecture.md](docs/architecture.md) — module map and data flow
- [docs/new-agent-walkthrough.md](docs/new-agent-walkthrough.md) — step-by-step
- [docs/brain-interface.md](docs/brain-interface.md) — Brain Protocol contract
- [docs/channel-interface.md](docs/channel-interface.md) — Channel Protocol
- [docs/skill-authoring.md](docs/skill-authoring.md) — how to write a SKILL.md
- [docs/permissions.md](docs/permissions.md) — tool whitelist merge logic
- [docs/security.md](docs/security.md) — tokens, gists, logs
- [docs/phase-2-roadmap.md](docs/phase-2-roadmap.md) — what is next

## Roadmap

- **Phase 1** (current): Claude Code brain + Telegram channel + 9 skill
  manifests; `kb-research` has working scripts.
- **Phase 2**: Slack/Discord adapters; port DeepTutor Slack integration.
- **Phase 3**: Additional brains (codex, antigravity).
- **Phase 4**: Local RAG via Ollama + embeddings, replacing file-read mode.

## License

MIT — see [LICENSE](LICENSE).
