# Brain Protocol

```python
class Brain(Protocol):
    async def invoke(self, inv: BrainInvocation) -> AsyncIterator[str]: ...
```

A brain consumes a `BrainInvocation` and yields text chunks. The runtime
is transport-agnostic: any module that satisfies this structural type is
a valid brain.

## BrainInvocation

| Field | Meaning |
|---|---|
| `agent_dir` | Working directory for the turn |
| `user_message` | Raw inbound text |
| `session_id` | Stable key for threading, `"<channel>:<chat_id>"` |
| `allowed_tools` | Final merged whitelist (see [permissions.md](permissions.md)) |
| `model` | Optional override |
| `timeout_s` | Hard wall-clock cap |
| `permission_mode` | Passed through to the underlying CLI |

## Errors

- Raise on transport failure or protocol-level errors. The runtime catches
  and logs; the user sees `(no response)`.
- Clean exits just stop iterating.

## Stub mode

Any brain should honor `COACH_BRAIN_STUB=1` by returning a canned reply
instead of doing real work — this keeps CI and smoke tests fast.
