# Intent classification playbook

Claude uses this decision tree during Step 1 of `SKILL.md`.

## Decision tree

```
Does the request name a specific clock time or day-of-week?
├── Yes  → CRON (produce a 5-field crontab string)
└── No
    └── Does the request specify a cadence interval?
        ├── Yes  → HEARTBEAT (produce "every Nm" / "every Nh")
        └── No
            └── Is it a single future moment?
                ├── Yes → ONE-OFF — decline politely, suggest /remind
                └── No  → Ask for clarification.
```

## Example utterances

| Utterance                                            | Mode      | Schedule tag         |
|------------------------------------------------------|-----------|----------------------|
| every morning at 8 send me a phrasal verb            | cron      | `0 8 * * *`          |
| daily drill at 19:00                                 | cron      | `0 19 * * *`         |
| weekdays 8am English quiz                            | cron      | `0 8 * * 1-5`        |
| Mondays 9:00 review flashcards                       | cron      | `0 9 * * 1`          |
| every Sunday evening review week                     | cron      | `0 20 * * 0`         |
| on the 1st of each month, reflection                 | cron      | `0 9 1 * *`          |
| every 2 hours check on me                            | heartbeat | `every 2h`           |
| ping me every 30 minutes                             | heartbeat | `every 30m`          |
| keep sending vocabulary frequently                   | heartbeat | `every 1h`           |
| every morning                                        | cron      | `0 8 * * *` (confirm)|
| weekly review                                        | cron      | `0 10 * * 0` (confirm)|
| tomorrow at 10am                                     | one-off   | redirect             |
| next Tuesday at 3pm                                  | one-off   | redirect             |

## Disambiguation rules

- **"every morning" without a specific hour** → default to `0 8 * * *`
  and confirm the time with the user in Step 1.
- **"weekly" without a weekday** → default to Sunday 10:00 and confirm.
- **"frequently" / "often"** → heartbeat `every 1h`, confirm.
- **Past tense / single day-of-week + single date** → one-off.
- When ambiguous, ask one clarifying question before running Step 2.

## Cron cheat-sheet

```
 ┌───── minute (0–59)
 │ ┌─── hour (0–23)
 │ │ ┌─ day-of-month (1–31)
 │ │ │ ┌─ month (1–12)
 │ │ │ │ ┌─ day-of-week (0=Sunday)
 │ │ │ │ │
 * * * * *
```

Only produce standard 5-field crontab strings. `croniter` validates
them at persistence time — invalid expressions are rejected with
`reason: invalid_cron_expression`.
