---
name: heartbeat-ops
version: 1.0.0
description: Add, remove, or rewrite entries in HEARTBEAT.md — the periodic task list.
required_tools: [Read, Edit, Write]
inputs:
  - action: enum(add|remove|rewrite|list)
  - entry: string — for add/rewrite
  - selector: string — text or index for remove/rewrite
outputs:
  - heartbeat_diff: markdown diff
triggers:
  - "remind me every"
  - "stop checking"
  - "change the heartbeat"
---

# Heartbeat Ops

## When to use

- Learner wants the coach to keep an eye on something recurrently.
- A task in HEARTBEAT.md is stale or wrong.
- The skill-evolver suggests a new standing task.

## How it works (playbook for Claude Code)

1. Parse `HEARTBEAT.md`. Entries live under `## Active` (checked each
   heartbeat) and `## Dormant` (temporarily disabled).
2. `add`: Append to `## Active` as ` - [ ] <entry>`.
3. `remove`: Match `selector` against entry text (case-insensitive prefix)
   or by 1-based index; move to `## Dormant` unless `--hard` is set.
4. `rewrite`: Replace a matched entry with the new text, preserving checkbox.
5. `list`: Return both sections as a numbered markdown list.
6. After any mutation, append an audit note under `## Log` at the bottom.

## Examples

> "Remind me every morning to log my food." → add to `## Active`.
>
> "Stop checking my goals weekly." → remove/match "goals".

## Constraints

- Keep `## Active` under 15 entries; if exceeded, nudge the learner to
  prune.
- Never delete the `## Log` trail.
- A heartbeat run must finish in under 30s; if the coach cannot evaluate
  every active entry in time, defer some to the next tick.
