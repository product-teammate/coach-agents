---
name: cron-ops
version: 1.0.0
description: Schedule one-off or recurring reminders via the runtime's APScheduler.
required_tools: [Read, Write, Bash]
inputs:
  - action: enum(add|remove|list)
  - when: string — ISO datetime OR cron expression ("0 9 * * MON")
  - message: string — text to send when the job fires
  - job_id: string — stable identifier, auto-generated if absent
outputs:
  - job_id
  - next_run: ISO datetime
triggers:
  - "remind me at"
  - "every monday morning"
  - "in 2 hours"
  - "cancel reminder"
---

# Cron Ops

## When to use

- Learner asks for a time-based reminder or recurring nudge.
- A skill (quiz-maker, flashcard-deck) wants to schedule a review.
- The coach decides a follow-up is warranted after a session.

## How it works (playbook for Claude Code)

1. Parse `when`:
   - If it matches `YYYY-MM-DDTHH:MM`, treat as one-off.
   - If it matches `* * * * *`, treat as cron.
   - If natural language ("in 2 hours", "tomorrow 9am"), resolve against
     `USER.md.timezone` and convert to ISO or cron.
2. Call the runtime helper:
   ```
   python -m runtime.scheduler add --agent <id> --when <expr> \
       --message "<msg>" [--job-id <id>]
   ```
3. Persist the job in `agents/<id>/.runtime/jobs.sqlite` (APScheduler
   JobStore). The runtime reloads jobs on startup.
4. Confirm to the learner with the next run time in their timezone.

## Examples

> "Remind me every weekday at 8am to review flashcards."
> → adds cron `0 8 * * MON-FRI`, message "Flashcard review".

## Constraints

- Do not schedule jobs more frequent than every 5 minutes.
- Cap per-agent jobs at 50; refuse new ones until some are removed.
- On removal, prefer `job_id` match; otherwise match by message prefix.
