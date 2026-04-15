# claude-code brain

Phase 1 brain. Spawns the `claude` CLI as a subprocess per turn and
streams stream-json events back to the runtime.

## Prerequisites

- `claude` on your PATH (verify with `claude doctor`).
- Either a logged-in session or `CLAUDE_CODE_OAUTH_TOKEN` exported.

## Stub mode

Set `COACH_BRAIN_STUB=1` to skip the subprocess and get canned replies.
Useful for CI, smoke tests, and running the rest of the stack locally
without the CLI.

## Arguments used

```
claude -p <user_message>
       --session <path>
       --output-format stream-json
       --permission-mode <mode>
       --allowed-tools <csv>
       [--model <name>]
```

Working directory is set to the agent directory so relative paths in
playbooks work out of the box.
