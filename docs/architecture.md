# Architecture

```
+------------------+       +--------------------+       +------------------+
|  channels/       |       |   runtime/         |       |   brains/        |
|  telegram, cli,  +------->  loader            +------->  claude_code    |
|  (slack, discord)|       |  router            |       |  (codex,        |
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
| `channels/cli/` | stdin/stdout REPL for dev |
| `runtime/loader.py` | Discover and validate agent.yaml files |
| `runtime/router.py` | Inbound message → brain → channel |
| `runtime/queue.py` | Per-user FIFO queue |
| `runtime/scheduler.py` | APScheduler wrapper |
| `runtime/permissions.py` | Merge agent + skill tool whitelists |
| `runtime/env.py` | Per-agent env_prefix helpers |
| `coach_cli/` | typer entry point and subcommands |
| `skills/` | Shared library of SKILL.md playbooks |
| `template/` | Starting point for `coach new` |

## Data flow per turn

1. Channel receives a message, constructs `InboundMessage`, calls `router.on_message`.
2. Router enqueues on the sender's queue (one in-flight subprocess per sender).
3. Worker builds `BrainInvocation` with merged tool whitelist.
4. Brain spawns `claude`, streams JSON events, yields text chunks.
5. Router collects chunks and sends a `Widget` back to the channel.
