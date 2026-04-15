---
name: quiz-maker
version: 1.0.0
description: Generate a quiz JSON from knowledge/, publish as a secret gist, and return a viewer URL.
required_tools: [Read, Write, Bash, WebFetch]
inputs:
  - topic: string — subject of the quiz
  - count: integer — number of questions, default 5
  - difficulty: enum(easy|medium|hard) — default medium
outputs:
  - gist_url: https://gist.github.com/...
  - viewer_url: https://.../viewer/?gist=<id>
triggers:
  - "quiz me"
  - "test me"
  - "make a quick quiz"
---

# Quiz Maker

## When to use

- Learner finishes a topic and wants a quick check.
- Coach proactively assesses after a research session.
- Periodic review triggered by `cron-ops`.

## How it works (playbook for Claude Code)

1. Gather source material: read `knowledge/_summaries/<topic>.md` and up to
   `max_docs_per_query` related files.
2. Compose a quiz object:
   ```json
   {
     "title": "CSS container queries",
     "difficulty": "medium",
     "questions": [
       {"q": "...", "choices": ["..."], "answer": 0, "explain": "..."}
     ]
   }
   ```
3. Validate: every question has 3-5 choices, exactly one `answer` index,
   an `explain` string, and no duplicate choices.
4. Publish as a secret gist:
   `gh gist create --filename quiz.json --public=false quiz.json`.
5. Construct viewer URL from `viewer.renderer_base` +
   `?gist=<gist_id>&mode=quiz`.
6. Send the viewer URL to the learner via the active channel. Log to
   MEMORY.md under `## Quizzes`.

## Examples

> "Quiz me on Playwright locators, 5 medium questions."
>
> Agent replies with `https://product-teammate.github.io/gist-render/viewer/?gist=abc123&mode=quiz`.

## Constraints

- Gist visibility: always honor `agent.yaml.viewer.gist_visibility`.
- Never include the answer index in any text the learner sees directly.
- If `GITHUB_TOKEN` or `gh` CLI is missing, fall back to saving the JSON
  under `agents/<id>/.runtime/quizzes/` and return a local path.
