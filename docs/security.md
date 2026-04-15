# Security

## Secrets

- All tokens live in environment variables; we never commit them.
- `.env` is gitignored; `.env.example` ships the contract.
- Each agent gets its own Telegram token via `env_prefix`. If a token
  leaks, rotate just that one.

## Gist visibility

`agent.yaml.viewer.gist_visibility` defaults to `secret`. Quiz and
flashcard gists are secret by default; they are discoverable only via
direct URL. Switch to `public` only if you actually want them listed.

## Allowed senders

`channels[].allow_from` gates the Telegram adapter. An empty list is
permissive (owner-only in practice, since only people with the bot
username can DM). Populate with numeric user IDs for production.

## Logs and sessions

- Session JSON files live under `agents/<id>/.runtime/sessions/` and are
  gitignored. They may contain personal content — back them up with the
  same care you give your chat history.
- The runtime's default log level is `info`; bump to `debug` with
  `agent.yaml.observability.log_level`.

## Tool permissions

See [permissions.md](permissions.md). Deny-by-default — the brain only
sees the tools the agent + its enabled skills request.
