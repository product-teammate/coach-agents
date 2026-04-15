# Create your first agent

This walkthrough covers both supported Phase 1 channels: **Slack** (the
two pre-built coaches Ava and Rook ship this way) and **Telegram**.

## 1. Scaffold

```bash
coach new my-coach
```

The CLI prompts for a display name, description, and channel. It copies
`template/` into `agents/my-coach/` and patches `agent.yaml`.

## 2. Write the persona

Edit `agents/my-coach/SOUL.md`. Replace the placeholder with an actual
coach identity: who they are, how they teach, what rules they follow.
This file is canonical — the runtime rebuilds `CLAUDE.md` from it every
turn. The existing `agents/english-coach/SOUL.md` and
`agents/playwright-coach/SOUL.md` are good references.

## 3. Fill in the learner profile

Edit `agents/my-coach/USER.md`. Set timezone, goals, current level. The
coach updates this file during the first calibration session.

## 4. Pick skills

```bash
coach add-skill my-coach kb-research
coach add-skill my-coach memory-ops
coach add-skill my-coach quiz-maker
coach add-skill my-coach flashcard-deck
coach add-skill my-coach heartbeat-ops
coach add-skill my-coach conversation-recap
```

## 5. Create the chat app

### Slack (Socket Mode)

1. <https://api.slack.com/apps> -> *Create New App* -> *From scratch*.
2. *Socket Mode* -> enable and generate an app-level token with
   `connections:write`. Save the `xapp-...` value.
3. *OAuth & Permissions* -> add bot scopes:
   `chat:write`, `reactions:write`, `app_mentions:read`,
   `channels:history`, `groups:history`, `im:history`, `im:read`,
   `files:write`.
4. *Event Subscriptions* -> enable and subscribe the bot to
   `message.im`, `message.channels`, `message.groups`, `app_mention`.
5. Install to workspace. Copy the `xoxb-...` bot token.

Quizzes and flashcards render via the gist-render viewer — the URL is
configured per agent under `viewer.renderer_base` in `agent.yaml`. Your
browser opens the viewer; Slack just posts the shareable link.

### Telegram

1. Talk to [@BotFather](https://t.me/BotFather), run `/newbot`, save
   the token.
2. In `agent.yaml`, set `channels.env_prefix: TELEGRAM_MY_COACH_` and
   `channels.mode: polling`.

## 6. Set the env

Copy `.env.example` to `.env` and fill in the tokens for this agent's
`env_prefix`:

```bash
# Slack
SLACK_MY_COACH_BOT_TOKEN=xoxb-...
SLACK_MY_COACH_APP_TOKEN=xapp-...

# Telegram
TELEGRAM_MY_COACH_BOT_TOKEN=123456:ABC-DEF...
```

## 7. Validate and start

```bash
coach validate my-coach
coach start my-coach        # filter to a single agent
# or
coach start --all           # run every agent
```

To iterate without the `claude` CLI installed or logged in:

```bash
COACH_BRAIN_STUB=1 coach start my-coach
```
