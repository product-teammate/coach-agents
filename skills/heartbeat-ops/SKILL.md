---
name: heartbeat-ops
version: 2.0.0
description: Add, list, and remove recurring tasks for this coach. Handles periodic (heartbeat) and calendar-time (cron) schedules.
required_tools: [Read, Write, Edit, Bash, Grep]
triggers:
  - user asks to "remind me", "every day", "weekly", "each morning", "keep sending", "ping me"
  - user asks to stop/cancel recurring
  - user asks "what are my scheduled tasks"
---

# Heartbeat Ops (v2)

Manage recurring tasks for this coach. Two storage backends share the
same five-step playbook:

- **HEARTBEAT.md** — periodic cadence (`every 2h`, `every 30m`). Ticked
  by the runtime every `interval_s`.
- **CRON.md** — calendar-time (`0 8 * * *` = every day at 08:00).
  Parsed by the runtime and re-read every 60s (hot-reload).

## Five-step playbook

Follow in order. Every step is required.

### Step 1 — Parse intent

Classify the user's natural-language request into exactly one of:

- **heartbeat**: periodic cadence, e.g. "every 2 hours", "every 30m",
  "ping me frequently", "keep checking".
- **cron**: a specific calendar moment, e.g. "every day at 8am",
  "Mondays 9:00", "weekdays 18:00".
- **one-off**: a single future moment, e.g. "tomorrow at 10am".
  Out of scope — redirect the user to a generic reminder tool.

See `playbook.md` for a 10+ utterance classification table.

Confirm the parsed schedule back to the user in one sentence before
continuing: _"Got it — every weekday at 08:00. Correct?"_

### Step 2 — ASK target (MANDATORY)

Even in a 1:1 DM, ask explicitly:

> Where should I send results? Reply with `dm` (this chat), `thread`
> (current thread), or `channel:<name>`.

Do **not** skip this. The step is what makes scheduling auditable.

### Step 3 — Validate channel

Run:

```bash
python -m coach_agents.scripts.check_channel --agent <agent-id> --target <target>
```

Parse the JSON stdout. On `ok: false` with `reason: not_in_channel`:

> I'm not in #<channel> yet. Please run this command in the channel:
>     /invite @<bot-display-name>
>
> Then tell me "I invited you" and I'll set up the recurring task.

Do **not** proceed to Step 4 unless `ok: true`.

### Step 4 — Persist

Periodic:

```bash
python -m coach_agents.scripts.add_task \
    --agent <agent-id> --mode heartbeat \
    --schedule "every 2h" \
    --task "Send 1 phrasal verb with 3 examples" \
    --target <chat_id-or-dm>
```

Calendar-time:

```bash
python -m coach_agents.scripts.add_task \
    --agent <agent-id> --mode cron \
    --schedule "0 8 * * *" \
    --task "Morning phrasal verb drill" \
    --target <chat_id-or-dm>
```

The runtime polls CRON.md every 60s; no restart needed.

### Step 5 — Confirm

Tell the user: parsed schedule, resolved target, first-run ETA, and how
to cancel:

> Say "stop the 8am phrasal verb" or edit HEARTBEAT.md / CRON.md by hand.

To cancel:

```bash
python -m coach_agents.scripts.remove_task --agent <agent-id> --match "<substring>"
```

## File formats

**HEARTBEAT.md** — under `## Active tasks`:

```
- [every 2h] Send 1 phrasal verb with 3 examples → target: D123ABC (added 2026-04-16T08:00Z)
```

**CRON.md** — under `## Active`:

```
- [0 8 * * *] Send 1 phrasal verb with 3 examples → target: D123ABC (added 2026-04-16T08:00Z)
```

The old checkbox format (`- [ ] task`) from v1 is superseded but still
parses safely — the runtime ignores lines it cannot match.

## Examples

**Happy path:**

> User: _every morning at 8am send me a phrasal verb_
> Coach: _Got it — every day at 08:00 local. Where should I send results (dm / thread / channel:name)?_
> User: _dm_
> Coach: _[runs check_channel --target dm → ok]_
> Coach: _[runs add_task --mode cron --schedule "0 8 * * *"]_
> Coach: _Scheduled. First run tomorrow 08:00 to this DM. Say "stop the 8am phrasal verb" to cancel._

**Channel not connected:**

> User: _every weekday 18:00 post drills to #english-study_
> Coach: _[check_channel --target channel:english-study → not_in_channel]_
> Coach: _I'm not in #english-study yet. Run `/invite @ava` there and tell me "done"._

## Constraints

- Do not persist anything until `check_channel` returns `ok: true`.
- Keep each file's Active section under 15 entries; nudge prune.
- Preserve the Completed / Disabled sections for audit.
