---
name: kb-research
version: 1.1.0
description: Research a topic from allowlisted sources and save clean markdown to the agent's knowledge/ directory.
required_tools: [WebFetch, Read, Write, Bash]
inputs:
  - topic: string — what to research
  - depth: enum(shallow|standard|deep) — effort level, default standard
outputs:
  - files: list of paths added to knowledge/
  - summary: markdown overview with links
triggers:
  - "research"
  - "look up"
  - "find info on"
  - "summarize this topic"
  - "add to my knowledge base"
---

# Knowledge Base Research

## When to use

- The learner asks to study a specific topic the agent does not already know.
- The learner drops a URL and asks for a digest.
- The coach needs background material before designing a quiz or flashcard set.
- `knowledge/` lacks a file that would answer the current question.
- The operator runs `coach learn <id>` (auto / targeted / batch / dry-run) — the
  CLI delegates to this skill for prompt grounding.

Do NOT use when: the answer is already covered by an existing knowledge file
(prefer reading it), or when the request is a chat-level clarification.

## Three ingestion modes (used by ``coach learn``)

1. **AUTO** — `coach learn <id>`. Read `SOUL.md` and `USER.md`, enumerate 5-10
   foundational topics from the learning arc, pick a source per topic from
   `sources.yaml`, fetch + clean each, and regenerate `knowledge/INDEX.md`.
2. **TARGETED** — `coach learn <id> "<topic>"`. Fetch 1-3 focused sub-files on
   that one topic. Split if broad; one mega-file is an anti-pattern.
3. **BATCH** — `coach learn <id> --from urls.txt`. Iterate the list, fetch
   each URL, skip anything not on the allowlist unless a `# override` comment
   precedes the URL in the batch file.

A fourth mode, **DRY-RUN** (`--dry-run`), only prints the AUTO plan and makes
no writes — useful to sanity-check what Claude would fetch before spending a
real run.

## How it works (playbook for Claude Code)

See [`playbook.md`](playbook.md) for the long-form prompt. Short version:

1. Parse the topic / read SOUL + USER; decide `depth` (default `standard`).
2. Consult `sources.yaml` allowlist — only fetch from approved domains.
3. Prefer `WebFetch` (the native tool) for normal cases; fall back to
   `scripts/fetch_and_clean.py <url> <output>` when you need a deterministic
   shell-out (e.g. heavy markdownify cleanup, non-interactive batch).
4. Each saved file must begin with YAML frontmatter: `topic`, `source`,
   `fetched_at` (ISO 8601), `tags`.
5. Regenerate `knowledge/INDEX.md` so a line exists per file with a
   one-sentence summary.
6. Reply to the learner/operator with: what was learned, which files were
   added, and a suggested next action (quiz? flashcards? deeper dive?).

## Examples

> **User**: "Research CSS container queries, standard depth."
>
> **Agent**:
> 1. Fetches MDN + web.dev + a CSS-Tricks primer via WebFetch.
> 2. Writes `knowledge/css-container-queries-mdn.md`,
>    `knowledge/css-container-queries-webdev.md`,
>    `knowledge/_summaries/css-container-queries.md`.
> 3. Replies: "Added 3 sources. Want a quick 5-question quiz?"

> **Operator**: `coach learn english-coach`
>
> **Agent** (AUTO): reads Ava's SOUL, plans topics such as CEFR descriptors,
> past simple vs. past continuous, conditionals overview, phrasal-verb
> clusters, register + formality. One file each, slug-stable, indexed.

## Constraints

- Only fetch from domains listed in `sources.yaml`.
- Respect `depth`: shallow = 1-2 sources, standard = 3-5, deep = up to 10.
- Strip scripts, navs, ads; keep headings, paragraphs, code, tables.
- Every saved file must start with a YAML header: `topic`, `source`,
  `fetched_at`, `tags`.
- Deterministic slugs: lowercase, kebab-case, no timestamps in filename.
- Never save a file larger than 200 KB — split or summarize instead.
