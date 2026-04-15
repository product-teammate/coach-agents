# SKILL.md authoring guide

Every skill under `skills/` is a folder with a `SKILL.md` at its root. The
first block of `SKILL.md` is YAML frontmatter validated against
[`schemas/skill.schema.json`](../../schemas/skill.schema.json).

## Frontmatter

```yaml
---
name: kebab-case-name            # unique, matches directory name
version: 1.0.0                   # semver
description: One-line purpose.
required_tools:                  # tools the brain needs for this skill
  - WebFetch
  - Read
  - Write
inputs:
  - topic: string — what to research
  - depth: enum(shallow|standard|deep) — default standard
outputs:
  - files: list of paths added to knowledge/
  - summary: markdown
triggers:                        # phrases / intents that should route here
  - "research"
  - "look up"
---
```

## Body sections (required)

### When to use
3-5 bullets, unambiguous conditions. Claude reads these and decides.

### How it works (playbook for Claude Code)
A numbered, step-by-step plan. If the steps exceed ~12, move detail into a
sibling `playbook.md` and link to it.

### Examples
One short concrete example: user prompt → agent actions → result.

### Constraints
Do / don't list. Include rate limits, allowlists, hard failures.

## Optional files

- `playbook.md` — long-form prompt Claude should execute.
- `sources.yaml` — allowlists, API endpoints, regex rules.
- `scripts/*.py` — deterministic helpers the brain can shell out to.
- `templates/*.md` — output scaffolds.

## Conventions

- Keep SKILL.md under 300 lines.
- Prefer deterministic scripts for anything network-facing.
- Never hard-code secrets; read from env.
- Document every output path relative to the agent's root.
