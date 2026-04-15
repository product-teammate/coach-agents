# Heartbeat tasks

The runtime wakes the coach on `proactive.heartbeat.interval_s` and asks it
to review this file. Each entry is a small recurring task the coach should
consider running — the coach decides whether to act or skip.

## Active

- [ ] Check USER.md for stale goals (> 30 days old).
- [ ] Review MEMORY.md for duplicate entries to prune.
- [ ] If no message from learner in 24h, draft a gentle nudge.

## Dormant
<!-- Move items here when temporarily disabled. -->
