# Telegram channel

Phase 1 channel. Long-polling via `python-telegram-bot` v21.

## Configuration

In `agent.yaml`:

```yaml
channels:
  - type: telegram
    enabled: true
    env_prefix: TELEGRAM_ENGLISH_   # reads TELEGRAM_ENGLISH_BOT_TOKEN
    allow_from: [123456789]         # your telegram user id
    mode: polling
```

Export the token before starting the runtime:

```bash
export TELEGRAM_ENGLISH_BOT_TOKEN=...
coach start english-coach
```

## Widgets

| Widget type         | Rendering                                          |
|---------------------|----------------------------------------------------|
| `text`              | HTML message (Markdown subset → HTML)              |
| `file`              | `send_document`                                    |
| `quiz_url`          | Message with the viewer URL                       |
| `flashcard_url`     | Message with the viewer URL                       |
