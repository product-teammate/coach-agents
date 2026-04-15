"""Publish a JSON payload as a GitHub gist via the ``gh`` CLI.

This helper is used by skills like ``quiz-maker`` and ``flashcard-deck`` to
persist a JSON artifact and return a shareable viewer URL.

Usage as a module:

    python -m coach_cli.publish_gist --filename quiz.json --desc "..." < input.json

Usage from Python:

    from coach_cli.publish_gist import publish_gist_json, viewer_url
    gist_id, raw = publish_gist_json({"title": "..."}, filename="quiz.json")
    url = viewer_url(raw, type="quiz",
                     renderer_base="https://product-teammate.github.io/gist-render/viewer/")
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote


class GistError(RuntimeError):
    """Raised when the ``gh`` CLI fails or is missing."""


def _require_gh() -> str:
    path = shutil.which("gh")
    if not path:
        raise GistError(
            "the `gh` CLI is not installed or not on PATH. "
            "Install from https://cli.github.com/ and run `gh auth login`."
        )
    return path


def publish_gist_json(
    content: dict,
    filename: str = "data.json",
    description: str = "",
    secret: bool = True,
) -> tuple[str, str]:
    """Create a gist containing one JSON file.

    Returns:
        (gist_id, raw_url) where raw_url points to the raw blob of the
        file inside the gist.
    """
    gh = _require_gh()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Use the requested filename so the gist file gets the right name.
        staged = tmp_dir / filename
        staged.write_text(json.dumps(content, indent=2), encoding="utf-8")

        args = [gh, "gist", "create", str(staged)]
        if not secret:
            args.append("--public")
        if description:
            args += ["--desc", description]

        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise GistError(
                f"gh gist create failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        gist_url = result.stdout.strip().splitlines()[-1].strip()

    gist_id = gist_url.rsplit("/", 1)[-1]
    raw_url = _resolve_raw_url(gh, gist_id, filename)
    return gist_id, raw_url


def _resolve_raw_url(gh: str, gist_id: str, filename: str) -> str:
    """Query the gist API for the raw_url of the named file."""
    result = subprocess.run(
        [gh, "api", f"/gists/{gist_id}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise GistError(
            f"gh api /gists/{gist_id} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GistError(f"gh api returned non-JSON: {exc}") from exc
    files = data.get("files") or {}
    entry = files.get(filename)
    if entry is None and files:
        entry = next(iter(files.values()))
    if not entry or "raw_url" not in entry:
        raise GistError(f"could not resolve raw_url for {filename} in gist {gist_id}")
    return str(entry["raw_url"])


def viewer_url(gist_raw_url: str, type: str, renderer_base: str) -> str:
    """Construct ``<renderer_base>?type=<type>&gist=<url-encoded raw url>``."""
    base = renderer_base.rstrip("/")
    encoded = quote(gist_raw_url, safe="")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}type={type}&gist={encoded}"


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a JSON file as a gist.")
    parser.add_argument("--filename", default="data.json")
    parser.add_argument("--desc", default="")
    parser.add_argument(
        "--public", action="store_true", help="Create a public (non-secret) gist."
    )
    parser.add_argument(
        "--type",
        default=None,
        help="If set, emit a viewer URL via --renderer-base.",
    )
    parser.add_argument(
        "--renderer-base",
        default="https://product-teammate.github.io/gist-render/viewer/",
    )
    parser.add_argument(
        "--input",
        default="-",
        help="Path to JSON input file, or '-' for stdin.",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(
        encoding="utf-8"
    )
    try:
        content = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON input: {exc}", file=sys.stderr)
        return 2

    try:
        gist_id, raw_url = publish_gist_json(
            content,
            filename=args.filename,
            description=args.desc,
            secret=not args.public,
        )
    except GistError as exc:
        print(f"gist publish failed: {exc}", file=sys.stderr)
        return 1

    out: dict[str, str] = {"gist_id": gist_id, "raw_url": raw_url}
    if args.type:
        out["viewer_url"] = viewer_url(raw_url, args.type, args.renderer_base)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli())
