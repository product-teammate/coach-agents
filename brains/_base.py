"""Brain Protocol — contract every brain adapter must satisfy.

A brain takes a structured invocation describing the agent's working
directory, the user's message, a session identifier, and the final
permission surface; it returns an async iterator of text chunks the
channel can forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Protocol


@dataclass(frozen=True)
class BrainInvocation:
    """One turn of work for a brain.

    Attributes:
        agent_dir: The per-agent directory (e.g. `agents/english-coach/`).
            The brain should set its cwd here.
        user_message: Raw inbound text from the channel.
        session_id: Stable key used to thread conversations. Typically
            ``"<channel>:<chat_id>"``. Used as the `--session` file name.
        allowed_tools: Final whitelist after merging agent-level and
            skill-level tool declarations.
        model: Optional model override. `None` means the brain picks.
        timeout_s: Hard wall-clock limit in seconds.
        permission_mode: Passed through to the underlying CLI, e.g.
            ``"acceptEdits"``.
    """

    agent_dir: Path
    user_message: str
    session_id: str
    allowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    timeout_s: int = 120
    permission_mode: str = "acceptEdits"
    request_id: str | None = None


class Brain(Protocol):
    """Structural type — implement `invoke` and you are a brain."""

    async def invoke(self, inv: BrainInvocation) -> AsyncIterator[str]:
        """Yield response chunks as the brain produces them.

        Chunks are text fragments suitable for streaming to a channel.
        Errors should raise; clean exits just stop yielding.
        """
        ...
