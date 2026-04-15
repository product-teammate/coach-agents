# kb-research — detailed playbook

You are extending the agent's knowledge base. Your job is to go from a topic
phrase to clean, attributed, summarized markdown stored in `knowledge/`.

## Step 1 — Understand the ask

Read the latest user message and `USER.md` to gauge the learner's level.
Decide:

- **topic slug**: kebab-case, under 50 chars.
- **depth**: `shallow` (1-2 sources), `standard` (3-5), `deep` (up to 10).
  Default `standard` unless the learner signals otherwise.

## Step 2 — Build a source plan

Load `skills/kb-research/sources.yaml`. Pick sources in this priority order:

1. Official primary (MDN, vendor docs, spec).
2. Reputable secondary (arxiv, wikipedia, canonical tutorials).
3. Community explainers — only if depth > shallow.

Skip anything not on the allowlist. If the topic has no matching source,
tell the learner and stop.

## Step 3 — Fetch and clean

For each chosen URL, call:

```
python skills/kb-research/scripts/fetch_and_clean.py <url> <output_path>
```

Where `<output_path>` is `knowledge/<topic-slug>-<source-slug>.md`. The
script fetches the URL with httpx, converts HTML to markdown via
markdownify, strips noise, and prepends a YAML header with `source`,
`fetched_at`, and `topic`.

## Step 4 — Cross-source summary

Call:

```
python skills/kb-research/scripts/summarize.py <path1> <path2> ...
```

It stitches key sections, de-duplicates, and writes
`knowledge/_summaries/<topic-slug>.md` (creating the dir if needed).

## Step 5 — Update MEMORY.md

Append a note to `MEMORY.md` under `## Research log`:

```
- 2026-04-14 — researched "CSS container queries" (standard) → 3 sources.
```

## Step 6 — Reply to the learner

Keep it short:

- One-paragraph TL;DR from the summary.
- List the files added with relative paths.
- Suggest the next concrete action (quiz, flashcards, practice task).
