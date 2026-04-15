"""`coach doctor` — verify the local environment is ready."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from runtime.loader import PROJECT_ROOT, discover_agents


console = Console()


def _check_binary(name: str) -> tuple[str, str]:
    path = shutil.which(name)
    if not path:
        return ("missing", "not on PATH")
    try:
        out = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=10
        )
        version = (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        version = f"failed: {exc}"
    return ("ok", version)


def _check_viewer(url: str) -> tuple[str, str]:
    try:
        import httpx  # type: ignore
    except ImportError:
        return ("skip", "httpx not installed")
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.head(url)
        return ("ok", f"HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return ("warn", str(exc))


def doctor() -> None:
    """Print a summary of environment health and exit 0 even on soft warnings."""
    table = Table(title="coach doctor")
    table.add_column("check")
    table.add_column("state")
    table.add_column("detail")

    py_state = "ok" if sys.version_info >= (3, 11) else "warn"
    table.add_row("python >= 3.11", py_state, sys.version.split()[0])

    for binary in ("claude", "gh"):
        state, detail = _check_binary(binary)
        table.add_row(binary, state, detail)

    stub = os.environ.get("COACH_BRAIN_STUB") == "1"
    table.add_row(
        "brain stub mode",
        "on" if stub else "off",
        "COACH_BRAIN_STUB=1 to skip claude CLI",
    )

    agents = []
    try:
        agents = discover_agents()
    except Exception as exc:  # noqa: BLE001
        table.add_row("agents", "error", str(exc))

    for loaded in agents:
        for ch in loaded.config.get("channels", []):
            if not ch.get("enabled"):
                continue
            ctype = ch.get("type")
            prefix = ch.get("env_prefix", "")
            if ctype == "telegram":
                required_keys = [f"{prefix}BOT_TOKEN"]
            elif ctype == "slack":
                required_keys = [f"{prefix}BOT_TOKEN", f"{prefix}APP_TOKEN"]
            else:
                continue
            for key in required_keys:
                state = "ok" if os.environ.get(key) else "missing"
                table.add_row(f"env {key}", state, loaded.agent_id)

        viewer = (loaded.config.get("viewer") or {}).get("renderer_base")
        if viewer:
            state, detail = _check_viewer(viewer)
            table.add_row(f"viewer {loaded.agent_id}", state, detail)

    if not agents:
        table.add_row("agents", "info", "none yet — run `coach new <id>`")

    console.print(table)
    console.print(f"project root: {PROJECT_ROOT}")
    raise typer.Exit(code=0)
