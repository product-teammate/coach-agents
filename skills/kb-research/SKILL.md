---
name: kb-research
version: 1.0.0
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

Do NOT use when: the answer is already covered by an existing knowledge file
(prefer reading it), or when the request is a chat-level clarification.

## How it works (playbook for Claude Code)

See [`playbook.md`](playbook.md) for the long-form prompt. Short version:

1. Parse the topic; decide `depth` (default `standard` = 3-5 sources).
2. Consult `sources.yaml` allowlist — only fetch from approved domains.
3. Call `scripts/fetch_and_clean.py <url>` for each source. It writes cleaned
   markdown to `knowledge/<slug>.md` and returns the path.
4. Call `scripts/summarize.py <paths...>` to produce a cross-source summary;
   save as `knowledge/_summaries/<topic-slug>.md`.
5. Reply to the learner with: what was learned, which files were added, and
   a suggested next action (quiz? flashcards? deeper dive?).

## Examples

> **User**: "Research CSS container queries, standard depth."
>
> **Agent**:
> 1. Fetches MDN + web.dev + a CSS-Tricks primer.
> 2. Writes `knowledge/css-container-queries-mdn.md`,
>    `knowledge/css-container-queries-webdev.md`,
>    `knowledge/_summaries/css-container-queries.md`.
> 3. Replies: "Added 3 sources. Want a quick 5-question quiz?"

## Constraints

- Only fetch from domains listed in `sources.yaml`.
- Respect `depth`: shallow = 1-2 sources, standard = 3-5, deep = up to 10.
- Strip scripts, navs, ads; keep headings, paragraphs, code, tables.
- Every saved file must start with a YAML header: `source`, `fetched_at`, `topic`.
- Never save a file larger than 200 KB — split or summarize instead.
