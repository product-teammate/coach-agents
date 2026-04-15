# Knowledge management

Each coach has a `knowledge/` directory under `agents/<id>/`. Phase 1 uses
plain markdown files — when the coach needs context, the brain just reads
them (`knowledge.mode: file-read` in `agent.yaml`). No vector DB, no
embeddings, no RAG server. Keep it boring.

## `coach learn` — four modes

```bash
coach learn <id>                      # AUTO: Claude plans topics from SOUL + USER
coach learn <id> "<topic>"            # TARGETED: one specific topic
coach learn <id> --from urls.txt      # BATCH: URL list, one per line
coach learn <id> --dry-run            # AUTO plan only, no writes
coach learn <id> --max 3              # Cap files fetched (useful for testing)
```

### When to use which

| Situation | Mode |
|---|---|
| Brand-new coach, need foundation material | AUTO |
| One specific gap surfaced in a session | TARGETED |
| You already curated the reading list | BATCH |
| Sanity-check what AUTO would do | `--dry-run` |

Under the hood, each mode spawns a one-shot `claude -p` with cwd set to the
agent's folder, tools limited to `Read, Write, Edit, WebFetch, Bash, Grep,
Glob`, and a 600-second timeout. Shared logic lives in
`coach_cli/learn_core.py` so the heartbeat consumer reuses it verbatim.

## Allowlist: `skills/kb-research/sources.yaml`

Only domains listed here may be fetched. When adding a new coach, extend
the list rather than turning off the check. Trust levels:

- `primary` — canonical docs (MDN, W3C, Cambridge, etc.).
- `secondary` — reputable reference (Wikipedia, arXiv).
- `community` — explainers, used sparingly.

BATCH mode lets you override with a `# override` comment above a URL in
the batch file. Use this only for audited one-off ingests.

## `knowledge/INDEX.md`

Regenerated after every `coach learn` run by
`coach_cli.commands._knowledge_index.regenerate_index`. Each line names
one file with a one-sentence summary pulled from the file's `topic`
frontmatter field (or the first heading). Alphabetical, stable.

## Manual curation

The directory is just markdown. You can:

- Drop in hand-written notes: `agents/<id>/knowledge/my-cheatsheet.md`.
  Prepend frontmatter with `topic`, `source: local`, `fetched_at`, `tags`
  to keep INDEX regeneration consistent.
- Edit a file Claude produced — there is no checksum or sync.
- Delete files. Re-run `coach learn <id>` to regenerate INDEX.md.

## ONBOARDING flow

`coach new <id>` asks whether to pre-load the knowledge base immediately.

- **Yes** — runs AUTO inline. Failure is non-fatal (bot creation still
  succeeds, a warning prints).
- **No** — writes `agents/<id>/ONBOARDING.md`. On the first heartbeat
  tick, `runtime/onboarding.py` parses the `## Pending` section and
  dispatches each task:
  - Tasks matching "Pre-load knowledge base" fire an AUTO `coach learn`.
  - Any other pending bullet is sent to the brain as a normal user
    message.
- Completed tasks move to `## Completed` with a UTC timestamp.
- When Pending is empty, the file is renamed to `ONBOARDING.done.md`
  (kept for audit, never auto-deleted).

Ordering inside the heartbeat tick is: **ONBOARDING first, then the
regular HEARTBEAT.md work.**

## How Claude reads knowledge during conversations

Phase 1 constraint: the brain just reads files. There is no retrieval
ranker. When the agent.yaml sets `knowledge.mode: file-read` and
`max_docs_per_query: N`, the runtime does not actually enforce N — that
cap is advisory. Claude uses its own `Read` tool on whichever files look
relevant, bounded by the tool whitelist.

## Scheduled re-research

Knowledge files are static once written, but the `heartbeat-ops` skill
(v2) can register recurring tasks that re-ingest or refresh a topic —
e.g. _"every Monday re-research the top 3 stale entries in
knowledge/"_. The skill persists these as cron lines in `CRON.md` and
the runtime fires them on schedule; each firing is a normal brain turn
with `WebFetch` and `Write` available. See
[scheduling.md](scheduling.md) for the playbook.

## Roadmap

Phase 2 introduces a local RAG option (Ollama embeddings + a tiny SQLite
vector index) for agents whose `knowledge/` outgrows file-read. See
[`phase-2-roadmap.md`](phase-2-roadmap.md).
