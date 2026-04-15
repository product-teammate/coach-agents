# Architecture

```
+------------------+       +--------------------+       +------------------+
|  channels/       |       |   runtime/         |       |   brains/        |
|  telegram, slack +------->  loader            +------->  claude_code    |
|  cli (discord P2)|       |  router            |       |  (codex,        |
|  python-telegram |       |  per-user queue    |       |   antigravity)  |
+------------------+       |  scheduler         |       +---------+--------+
        ^                  |  permissions       |                 |
        |                  +---------+----------+                 | subprocess
        | Widget                      |                           v
        |                             |                  +------------------+
        |                             |                  | `claude` CLI     |
        |                             |                  | stream-json      |
        |                             |                  +---------+--------+
        |                             |                            |
        |                             v                            v
        |                   +---------+----------+        +-----------------+
        |                   |  agents/<id>/      |        |  skills/        |
        +-------------------+  SOUL / USER /     |        |  kb-research    |
                            |  MEMORY / HEART /  |        |  quiz-maker     |
                            |  knowledge/        |        |  flashcard-deck |
                            +--------------------+        |  memory-ops     |
                                                          |  heartbeat-ops  |
                                                          |  cron-ops       |
                                                          |  skill-evolver  |
                                                          |  conversation-  |
                                                          |     recap       |
                                                          |  knowledge-     |
                                                          |     ingest      |
                                                          +-----------------+
```

## Module map

| Module | Responsibility |
|---|---|
| `brains/_base.py` | Brain Protocol and BrainInvocation dataclass |
| `brains/claude_code/adapter.py` | Subprocess + stream-json parser |
| `brains/claude_code/claude_md_builder.py` | Compose CLAUDE.md per turn |
| `channels/_base.py` | Channel Protocol, InboundMessage, Widget |
| `channels/telegram/` | python-telegram-bot v21 long-polling adapter |
| `channels/slack/` | slack_sdk Socket Mode adapter (Phase 1) |
| `channels/cli/` | stdin/stdout REPL for dev |
| `runtime/loader.py` | Discover and validate agent.yaml files; honors `COACH_ONLY_AGENT` and `COACH_AGENTS_ROOT` |
| `runtime/__main__.py` | Top-level `python -m runtime` entry; wires channels, router, and heartbeat scheduler |
| `runtime/router.py` | Inbound message -> brain -> channel |
| `runtime/queue.py` | Per-user FIFO queue |
| `runtime/scheduler.py` | APScheduler wrapper (heartbeat jobs) |
| `runtime/permissions.py` | Merge agent + skill tool whitelists |
| `runtime/env.py` | `.env` loader and `<prefix><key>` helpers |
| `coach_cli/` | Typer entry point and subcommands |
| `coach_cli/publish_gist.py` | Shared JSON-to-gist publisher used by quiz-maker / flashcard-deck |
| `skills/` | Shared library of SKILL.md playbooks |
| `template/` | Starting point for `coach new` |
| `agents/english-coach/` | Ava — live English coach (Slack) |
| `agents/playwright-coach/` | Rook — live Playwright automation coach (Slack) |

## Data flow per turn

1. Channel receives a message, constructs `InboundMessage`, calls `router.on_message`.
2. Router enqueues on the sender's queue (one in-flight subprocess per sender).
3. Worker builds `BrainInvocation` with merged tool whitelist.
4. Brain spawns `claude`, streams JSON events, yields text chunks.
5. Router collects chunks and sends a `Widget` back to the channel.

## Heartbeat loop

1. On startup, `runtime/__main__.py` inspects each agent's
   `proactive.heartbeat` block. When `enabled: true`, `CoachScheduler`
   registers an `interval` APScheduler job at `interval_s` cadence.
2. Each tick reads `HEARTBEAT.md`, strips headers and template
   commentary, and — if any real task content remains — spawns a
   synthetic brain turn using a system prompt prefixing
   "Execute the following periodic tasks from HEARTBEAT.md" + the file
   content.
3. The produced reply is posted via the agent's first started channel
   to `proactive.heartbeat.target_chat_id` (if configured).
4. `proactive.cron.enabled: true` wires `runtime/cron_loader.py`, which
   parses `agents/<id>/CRON.md` into individual APScheduler jobs. A
   60-second polling job (configurable via `COACH_CRON_POLL_S`) re-reads
   the file and reconciles — new lines register, removed lines
   unregister, unchanged lines are left in place. No restart required
   when skills add or remove entries. See [scheduling.md](scheduling.md)
   for the file format and the `heartbeat-ops` skill for the five-step
   playbook (parse → ask target → check channel → persist → confirm).
