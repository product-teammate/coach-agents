---
name: knowledge-ingest
version: 1.0.0
description: Re-index knowledge/ after changes and cross-link related files.
required_tools: [Read, Write, Edit, Bash]
inputs:
  - scope: enum(all|changed) — default changed
outputs:
  - files: updated knowledge/INDEX.md
  - cross_links: inline references added to related files
triggers:
  - "re-index knowledge"
  - "new docs added"
  - "sync knowledge base"
---

# Knowledge Ingest

## When to use

- After `kb-research` writes new files.
- When the learner manually drops a markdown file into `knowledge/`.
- On a heartbeat, if `knowledge/INDEX.md` is older than the newest doc.

## How it works (playbook for Claude Code)

1. List every `.md` under `knowledge/` (ignore `_summaries/INDEX.md`).
2. Parse each file's frontmatter for `source`, `topic`, `slug`.
3. Build `knowledge/INDEX.md` grouped by topic, each entry linking to its
   file with a one-line abstract.
4. For each file, scan for topic-like phrases that match other files'
   slugs. When found, insert a `See also:` block near the top (idempotent —
   do not duplicate).
5. Append a MEMORY.md entry under `## Knowledge ingest log`.

## Examples

> New file `knowledge/playwright-locators.md` arrives. Agent detects it
> references "selectors" — already covered in
> `knowledge/playwright-selectors.md`. Both files gain a mutual
> `See also:` link.

## Constraints

- Never delete content. Only add headers, links, and the INDEX.
- Cross-link blocks must be wrapped in `<!-- kb-auto -->` markers so they
  can be regenerated cleanly.
- Stop after 60 seconds; re-queue if more work remains.
