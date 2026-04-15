---
name: skill-evolver
version: 1.0.0
description: Weekly analysis of session history to propose new/updated/deprecated skills.
required_tools: [Read, Write, Glob, Grep, Bash]
inputs:
  - window_days: integer — default 7
outputs:
  - file: agents/<id>/SUGGESTIONS.md
  - notification: short channel message to the owner
triggers:
  - weekly cron ("0 9 * * MON")
  - "review my skills"
  - "what should we change"
---

# Skill Evolver

The feedback loop. Reads the last N days of sessions, compares to the
currently enabled skills, and proposes changes. It does NOT modify the
skills library itself — it writes a plan, the owner approves.

## When to use

- On the weekly cron (default Monday 09:00 local).
- When the learner explicitly asks for a review.
- After a major onboarding change (goal added, new domain).

## How it works

See [`playbook.md`](playbook.md) — it is the full analysis prompt that
Claude Code should execute end to end.

## Output shape

`agents/<id>/SUGGESTIONS.md`:

```
# Skill review — 2026-04-14

## Summary
<2-4 bullets of observed patterns>

## [NEW SKILL] candidates
### <proposed-name>
Frontmatter draft + "when to use" section.

## [IMPROVE] to existing skills
### <skill>
What changed in usage; suggested edits.

## Deprecate
- <skill> — unused since 2026-03-20
```

## Constraints

- Must run in under 3 minutes of wall time.
- Must not modify any SKILL.md automatically. Writing to SUGGESTIONS.md
  is the only side effect inside the agent directory.
- Must post a one-line notification so the owner actually reads it.
