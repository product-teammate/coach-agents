"""Claude Code session file helpers.

A session is just a JSON file on disk the `claude` CLI reads/writes. We
hash the logical session_id to a filename-safe slug and keep it under the
agent's `.runtime/sessions/` directory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def session_path(agent_dir: Path, session_id: str) -> Path:
    """Return the session JSON path for an agent+session pair.

    Creates the parent directory if needed.
    """
    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:16]
    sessions_dir = agent_dir / ".runtime" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir / f"{digest}.json"
