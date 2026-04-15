# kb-research — detailed playbook

You are extending the agent's knowledge base. Your job is to go from a topic
phrase (or the coach's persona itself) to clean, attributed, summarized
markdown stored in `knowledge/`.

## Mode A — AUTO (triggered by ``coach learn <id>``)

**Step A1 — Read the coach.**
Open `SOUL.md` and `USER.md`. Identify:

- The coach's teaching domain (English? Playwright? Math?).
- The learning arc stages (CEFR levels, test pipeline maturity, etc.).
- The learner's current level, goals, and growth edges (if USER.md is filled
  in — otherwise assume the earliest stage of the arc).

**Step A2 — Enumerate foundational topics.**
Produce 5-10 topic candidates that the coach will repeatedly need. Bias
toward the lower stages of the arc (the learner is usually closer to the
start than the end). Examples:

- English A2→C1 coach: CEFR level descriptors, past simple vs. past
  continuous, conditionals overview, register + formality, collocations
  basics, phrasal-verb clusters for daily life.
- Playwright coach: selector strategy, locator vs. element handle, auto-wait
  mechanics, test parallelism, CI integration recipes, trace viewer.

**Step A3 — Pick a source per topic.** Load
`skills/kb-research/sources.yaml`. Priority:

1. Official primary (MDN, Playwright docs, W3C, Cambridge, British Council).
2. Reputable secondary (Wikipedia context, arXiv).
3. Community explainers — only if primary doesn't cover the angle.

Skip anything not on the allowlist.

**Step A4 — Fetch + clean.** For each URL use `WebFetch` to retrieve, then
write `knowledge/<slug>.md` with frontmatter:

```
---
topic: <topic>
source: <url>
fetched_at: <ISO 8601>
tags: [<tag1>, <tag2>]
---
```

Slugs are lowercase kebab-case, deterministic (no timestamps). Target
500-3000 words per file. If one source would overflow, split into focused
sub-files.

**Step A5 — Regenerate INDEX.** Write (or overwrite) `knowledge/INDEX.md`
with one bullet per file: ``- `<slug>.md` — <one-sentence summary>``. Sorted
alphabetically by filename. The `coach learn` CLI will also run this
automatically after you finish.

## Mode B — TARGETED (``coach learn <id> "<topic>"``)

Same as AUTO steps A3-A5 but scoped to the single topic. If the topic is
broad, split into 2-3 focused sub-files rather than one mega-file.

## Mode C — BATCH (``coach learn <id> --from urls.txt``)

Iterate the URL list in order. For each URL:

1. Check the allowlist. Skip if not allowed **unless** the batch file
   contains a line like `# override` immediately above this URL.
2. Fetch via WebFetch, clean, save to `knowledge/<slug>.md` with
   frontmatter (source = the URL).
3. Update `knowledge/INDEX.md`.

## Mode D — DRY-RUN (``coach learn <id> --dry-run``)

Execute Mode A steps A1-A3 only. Print the plan (topics + URLs) and stop.
Do NOT call WebFetch and do NOT write any files.

## Step — Update MEMORY.md

Append a note to `MEMORY.md` under `## Research log`:

```
- 2026-04-14 — coach learn run (auto, N files).
```

## Step — Reply

Keep it short:

- One-paragraph TL;DR of what was added (or planned, for dry-run).
- List the files added with relative paths.
- Suggest the next concrete action (quiz, flashcards, practice task).

## Hard rules

- Only fetch from allowlisted domains unless a `# override` comment
  authorises it in a batch file.
- Max 10 files per run.
- If a single fetch fails, log the error and continue — do not abort the
  whole batch.
- De-duplicate — don't fetch two pages on the same concept.
- Never save a file > 200 KB; split instead.
