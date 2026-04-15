---
name: flashcard-deck
version: 1.0.0
description: Generate a flashcard deck JSON from knowledge/, publish as a secret gist, and return a viewer URL.
required_tools: [Read, Write, Bash]
inputs:
  - topic: string
  - count: integer — default 10
  - style: enum(basic|cloze|image) — default basic
outputs:
  - gist_url
  - viewer_url
triggers:
  - "flashcards"
  - "make me a deck"
  - "spaced repetition"
---

# Flashcard Deck

## When to use

- Learner wants to drill vocabulary, definitions, or short facts.
- After a research session, to lock in key terms.
- As a warm-up on a heartbeat cycle.

## How it works (playbook for Claude Code)

1. Pull relevant sections from `knowledge/` summaries and source docs.
2. Build deck JSON:
   ```json
   {
     "title": "...",
     "style": "basic",
     "cards": [
       {"front": "...", "back": "...", "tags": ["css", "container-queries"]}
     ]
   }
   ```
3. Validate: unique fronts, non-empty backs, 1-5 tags each.
4. Publish as a secret gist with filename `deck.json`.
5. Build viewer URL: `renderer_base + ?gist=<id>&mode=flashcards`.
6. Log to MEMORY.md under `## Decks`, with the deck slug and due-review
   date (24 hours out).

## Examples

> "Make me a 10-card deck on Playwright locators."
>
> Agent posts the viewer URL and schedules a review reminder via
> `cron-ops` for the next day.

## Scripts

Prefer the shared publisher over raw `gh gist create` (requires the
`Bash` tool):

```bash
echo '<deck-json-here>' | python -m coach_cli.publish_gist \
    --filename deck.json \
    --desc "Flashcards: <topic>" \
    --type flashcards \
    --renderer-base https://product-teammate.github.io/gist-render/viewer/
```

The script prints a JSON object with `gist_id`, `raw_url`, and a
constructed `viewer_url`. Post the `viewer_url` to the learner.

Python API (when a direct-run tool is available):

```python
from coach_cli.publish_gist import publish_gist_json, viewer_url
gist_id, raw_url = publish_gist_json(
    deck, filename="deck.json", description=f"Flashcards: {topic}", secret=True
)
url = viewer_url(raw_url, type="flashcards", renderer_base=renderer_base)
```

## Constraints

- Avoid duplicating content from existing decks on the same topic —
  check MEMORY.md first.
- Keep fronts under 120 chars and backs under 400 chars.
- Respect gist visibility from agent.yaml.
