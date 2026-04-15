# Create your first agent

## 1. Scaffold

```bash
coach new english-coach
```

Picks the channel, patches `agent.yaml`, copies `template/` into
`agents/english-coach/`.

## 2. Write the persona

Edit `agents/english-coach/SOUL.md`. Replace the placeholder with an
actual coach identity: who they are, how they teach, what rules they
follow. This file is canonical — the runtime rebuilds `CLAUDE.md` from it
every turn.

## 3. Fill in the learner profile

Edit `agents/english-coach/USER.md`. Set timezone, goals, current level.

## 4. Pick skills

```bash
coach add-skill english-coach kb-research
coach add-skill english-coach memory-ops
coach add-skill english-coach quiz-maker
```

## 5. Set the env

Copy `.env.example` to `.env` and fill in the Telegram token for this
agent's `env_prefix`.

## 6. Validate and start

```bash
coach validate english-coach
coach start --all
```

To iterate without the `claude` CLI installed:

```bash
COACH_BRAIN_STUB=1 coach start --all
```
