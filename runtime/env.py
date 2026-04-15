"""Per-agent environment resolution via env_prefix.

We read `os.environ` (optionally augmented by a `.env` file) and expose
helpers to pull `<PREFIX>KEY` values.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    """Very small .env loader — no external dependency.

    Lines of the form ``KEY=VALUE`` are loaded into os.environ unless the
    key is already set.
    """
    target = path or Path.cwd() / ".env"
    if not target.exists():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_env(prefix: str, key: str, default: str | None = None) -> str | None:
    """Look up `<prefix><key>` in the environment."""
    return os.environ.get(f"{prefix}{key}", default)


def require_env(prefix: str, key: str) -> str:
    """Look up `<prefix><key>` or raise a helpful error."""
    value = get_env(prefix, key)
    if not value:
        raise RuntimeError(
            f"missing required env var {prefix}{key}; "
            f"set it in .env or export it before starting the runtime"
        )
    return value
