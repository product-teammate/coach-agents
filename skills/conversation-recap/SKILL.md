---
name: conversation-recap
version: 1.0.0
description: Summarize recent session history for continuity across gaps.
required_tools: [Read, Write]
inputs:
  - window: enum(session|day|week) — default session
outputs:
  - recap: short markdown (< 40 lines)
  - memory_updates: entries to push into MEMORY.md
triggers:
  - "where did we leave off"
  - "catch me up"
  - "what did we cover last time"
---

# Conversation Recap

## When to use

- Learner returns after a gap and opens a new session.
- Before a long pedagogical task, to re-ground on recent context.
- At session end, to distill takeaways before the context is lost.

## How it works (playbook for Claude Code)

1. Pick the session source based on `window`:
   - `session` — the last JSONL file in `.runtime/sessions/`.
   - `day` — concatenate files from the last 24 hours.
   - `week` — last 7 days.
2. Extract: topics covered, questions asked, decisions made, skills used.
3. Produce a recap with four short sections:
   - Where we were
   - What we covered
   - What's still open
   - Suggested next step
4. Send the recap to the learner.
5. Optionally, queue 1-5 MEMORY.md updates via `memory-ops` (append with
   today's date under the right category).

## Examples

> Learner returns after 3 days. Agent replies with a 6-bullet recap and
> asks: "Pick up the irregular verbs drill, or switch gears?"

## Constraints

- Keep recap under 300 words.
- Never invent events that are not in the session files.
- Redact anything the learner explicitly asked to forget (consult MEMORY's
  `## Do not mention` section if present).
