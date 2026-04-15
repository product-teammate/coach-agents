# Slack channel

Socket-Mode Slack adapter built on [`slack_sdk`](https://slack.dev/python-slack-sdk/).
No public webhook is required — your bot dials out over a websocket.

## Setup

1. Create a Slack app at <https://api.slack.com/apps> (or reuse an
   existing one).
2. Enable **Socket Mode** under *Settings -> Socket Mode*. Generate an
   app-level token with scope `connections:write` — this is the
   `xapp-...` token.
3. Under *OAuth & Permissions*, add bot scopes:
   `chat:write`, `reactions:write`, `channels:history`, `groups:history`,
   `im:history`, `im:read`, `app_mentions:read`, `files:write`.
   Install the app to your workspace and copy the bot token — this is the
   `xoxb-...` token.
4. Under *Event Subscriptions*, enable events and subscribe the bot to:
   `message.im`, `message.channels`, `message.groups`, `app_mention`.
5. Export both tokens with the env prefix your agent uses:

   ```bash
   export SLACK_ENGLISH_BOT_TOKEN=xoxb-...
   export SLACK_ENGLISH_APP_TOKEN=xapp-...
   ```

## Config in `agent.yaml`

```yaml
channels:
  - type: slack
    enabled: true
    env_prefix: SLACK_ENGLISH_
    allow_from: ["*"]        # or explicit list of Slack user ids
    group_policy: mention    # open | mention | allowlist
    reply_in_thread: true
    react_emoji: eyes
```

`env_prefix` is the shared prefix — the adapter reads
`<prefix>BOT_TOKEN` and `<prefix>APP_TOKEN`.

## Behavior

- DMs: replies inline (no thread).
- Channels: replies inside a thread when `reply_in_thread: true`.
- Reacts with `:eyes:` on receipt (configurable via `react_emoji`).
- Converts Markdown -> Slack mrkdwn via
  [`formatting.py`](formatting.py); code fences are preserved.
- `quiz_url` / `flashcard_url` widgets post the URL prefixed with a
  small intro and unfurl enabled so Slack renders a preview card.
