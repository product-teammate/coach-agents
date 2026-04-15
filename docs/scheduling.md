# Scheduling — HEARTBEAT.md and CRON.md

Two mechanisms drive proactive coach behaviour. Both are backed by
APScheduler inside the runtime. Both accept new entries without a
process restart.

## Heartbeat — periodic cadence

Per-agent configuration:

```yaml
proactive:
  heartbeat:
    enabled: true
    interval_s: 1800
    file: HEARTBEAT.md
```

Every `interval_s` seconds the runtime reads `HEARTBEAT.md`, strips the
template prose, and if anything actionable remains passes it to the
brain as a synthetic user turn. The reply (if any) is sent to
`proactive.heartbeat.target_chat_id`.

File format (active section):

```
## Active tasks

- [every 2h] Send 1 phrasal verb with 3 examples → target: D123ABC (added 2026-04-16T08:00Z)
```

Lines are free-form — Claude decides each tick which tasks are due
based on the schedule tag and any local metadata.

## Cron — calendar-time

Per-agent configuration:

```yaml
proactive:
  cron:
    enabled: true
```

`CRON.md` lives in the agent directory. Lines under `## Active` are
parsed by `runtime.cron_loader` and registered with APScheduler
directly — each line becomes its own cron job. Every `COACH_CRON_POLL_S`
seconds (default 60) the runtime re-reads `CRON.md` and reconciles:

- New lines → register new jobs.
- Removed lines → unregister jobs.
- Unchanged lines → left alone.

File format:

```
## Active

- [0 8 * * *] Morning phrasal verb drill → target: D123ABC (added 2026-04-16T08:00Z)
- [0 9 * * 1] Weekly review → target: C456DEF (added 2026-04-16T08:00Z)

## Disabled

- [0 20 * * *] Evening wrap (disabled 2026-04-10T18:00Z)
```

## How "where should I send results?" works

The `heartbeat-ops` skill makes this question mandatory. Valid targets:

- `dm` — send to the requesting user's DM. Always valid for Slack
  because the inbound message guarantees the bot can reply.
- `thread` — current thread. Also always valid.
- `channel:<name>` — a named Slack channel. Requires the bot to be a
  member; the `check_channel` script verifies via
  `conversations.members` before anything is persisted.

If the bot is not in the target channel, Claude tells the user to run
`/invite @<bot>` in that channel before setup can complete.

## Cancelling tasks

Three options:

1. Ask the coach in natural language ("stop the 8am phrasal verb"). The
   `heartbeat-ops` skill calls `remove_task.py --match "phrasal verb"`.
2. Run the script directly:
   ```bash
   python -m coach_agents.scripts.remove_task --agent english-coach --match "phrasal verb"
   ```
3. Edit `HEARTBEAT.md` or `CRON.md` by hand. The cron poller picks up
   the change within 60 seconds.

Disabled lines are preserved under `## Completed` (heartbeat) or
`## Disabled` (cron) with a `(disabled <ISO>)` marker for audit.
