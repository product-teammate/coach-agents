# skill-evolver — weekly analysis playbook

You are acting as the coach's quality-improvement loop. Your job today is to
produce `agents/<id>/SUGGESTIONS.md` — a prioritized, actionable proposal
for how this agent's skill set should change.

## Inputs to read

1. **Sessions** — `.runtime/sessions/*.json` (JSONL per-turn records).
   Parse every file modified in the last `window_days` (default 7). Each
   line is a message object with `role`, `content`, and optionally
   `tool_calls` and `skill_hint`.

2. **Agent config** — `agent.yaml`. Note `skills:` (currently enabled),
   `viewer.renderer_base`, and `brain.allowed_tools`.

3. **Skill manifests** — for each name in `skills:`, read
   `skills/<name>/SKILL.md` (the SHARED library at the project root).
   Capture: `description`, `triggers`, and the "When to use" bullets.

4. **Learner profile** — `USER.md` and `MEMORY.md` for context on goals.

## Analysis steps

### Step A — Cluster user requests

Walk every user turn in the window. Extract the learner's intent in a short
phrase ("wants vocabulary drill", "wants explanation of a grammar rule",
"wants reminder set"). Cluster by similarity; count per cluster.

### Step B — Map intents to skills

For each cluster, ask: did a skill handle it, or did Claude improvise?
Evidence: presence of `skill_hint` or tool-call patterns matching a skill's
`required_tools`. Record:

- `skill_hit` — skill triggered, outcome looked good.
- `skill_miss` — skill triggered, user follow-up suggests it missed.
- `ad_hoc` — no skill triggered; Claude solved it manually.
- `unserved` — Claude deflected or gave a weak response.

### Step C — Propose changes

**NEW SKILL candidate** if:
- A cluster has 3+ `ad_hoc` or `unserved` hits in the window, AND
- The workflow is reproducible (not a one-off creative task).

Draft frontmatter for the new skill:

```yaml
name: <kebab>
version: 0.1.0
description: <one line>
required_tools: [<tools Claude actually used>]
triggers: [<top 3 phrases from the cluster>]
```

Then write a "When to use" section with 3-5 bullets drawn from the
clustered requests.

**IMPROVE an existing skill** if:
- `skill_miss` count > `skill_hit` count, OR
- Triggers in SKILL.md don't match the phrases users actually say.

For each, list: current shortfall, suggested edit (no code — just intent).

**Deprecate** if:
- A skill has zero hits in 14 days AND isn't structurally required (e.g.
  `memory-ops` is always needed; never deprecate the "always-on" skills).

### Step D — Write SUGGESTIONS.md

Overwrite `agents/<id>/SUGGESTIONS.md` with the structure defined in the
SKILL.md. Use today's date in the H1. Keep it under 300 lines.

### Step E — Notify the owner

Send a single message on the active channel:

> "Weekly skill review ready. Open SUGGESTIONS.md — I proposed N new
> skills, M improvements, K deprecations."

Include a short bullet list of the top 3 proposals.

## Guardrails

- Do NOT edit `skills/*` directly.
- Do NOT change `agent.yaml.skills`.
- If no meaningful changes are warranted, still write SUGGESTIONS.md with
  a "No changes recommended this week" note and a one-line notification.
- Wall-clock budget: 3 minutes. If analysis is incomplete, include a
  `## Incomplete — continue next run` section.
