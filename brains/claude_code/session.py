"""Claude Code session helpers.

Claude CLI 2.x persists sessions in ``~/.claude/`` keyed by a UUID passed
via ``--session-id``. We derive a deterministic UUIDv5 from the
(agent_dir, session_id) pair so the same logical conversation always maps
to the same claude session.
"""

from __future__ import annotations

import uuid
from pathlib import Path

_NAMESPACE = uuid.UUID("6f1d4c2a-1a3b-4b9e-8c2a-9d1f5c7e2b10")


def session_uuid(agent_dir: Path, session_id: str) -> str:
    """Return a deterministic UUID string for the given agent+session pair."""
    name = f"{agent_dir.resolve()}::{session_id}"
    return str(uuid.uuid5(_NAMESPACE, name))
