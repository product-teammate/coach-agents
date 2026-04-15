---
name: memory-ops
version: 1.0.0
description: Structured read/write to MEMORY.md with categorization, dedupe, and pruning.
required_tools: [Read, Edit, Write]
inputs:
  - action: enum(append|categorize|dedupe|prune|read)
  - entry: string — for append/categorize
  - category: string — optional override
outputs:
  - memory_diff: markdown diff of changes
triggers:
  - "remember that"
  - "forget that"
  - "what do you know about me"
  - heartbeat dedupe pass
---

# Memory Ops

## When to use

- Every user message that reveals persistent facts ("I'm B2 in Spanish",
  "my exam is May 10").
- When `MEMORY.md` exceeds 800 lines (trigger dedupe/prune).
- On a heartbeat to promote short-term notes into the right category.

## How it works (playbook for Claude Code)

1. Read `MEMORY.md`. Parse its `##` headings as categories. Standard
   categories: `Facts`, `Preferences`, `Goals`, `Quizzes`, `Decks`,
   `Research log`, `Knowledge ingest log`, `Scratch`.
2. For `append`:
   - Classify `entry` into an existing category or `Scratch`.
   - Check for near-duplicates (case-insensitive prefix match); skip if dupe.
   - Append with an ISO date prefix: `- 2026-04-14 — <entry>`.
3. For `dedupe`:
   - Within each category, merge entries whose first 60 chars match.
   - Preserve the newest timestamp.
4. For `prune`:
   - Drop `Scratch` entries older than 30 days.
   - Archive `Quizzes`/`Decks` older than 90 days to
     `MEMORY.archive.md`.
5. For `read`:
   - Return the most relevant 20 entries given the current user message.

## Examples

> User: "Remember I have a TOEFL exam on May 10."
> Action: append → `## Goals`: `- 2026-04-14 — TOEFL exam on May 10.`

## Constraints

- Never rewrite the learner's own words without flagging it in the diff.
- Keep entries to one line. For longer notes, link to a file under
  `knowledge/notes/`.
- Always report what changed in the final reply, so the learner can correct.
