"""Fetch a URL and save cleaned markdown under an agent's knowledge/ directory.

Usage:
    python fetch_and_clean.py <url> <output_path>

The script is intentionally small and deterministic so Claude Code can shell
out to it without prompt-engineering a whole fetcher. Phase 1 ships stub
behavior when dependencies are missing; it still creates the output file so
the rest of the playbook can proceed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _slugify(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe or "source"


def _fetch(url: str) -> str:
    try:
        import httpx  # type: ignore
    except ImportError:
        return f"<!-- TODO: install httpx to fetch {url} -->"
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        resp = client.get(url, headers={"User-Agent": "coach-agents/0.1"})
        resp.raise_for_status()
        return resp.text


def _to_markdown(html: str) -> str:
    try:
        from markdownify import markdownify as md  # type: ignore
    except ImportError:
        return "TODO: install markdownify to convert HTML.\n\n" + html[:2000]
    return md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    _, url, output_path = argv
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        print(f"refusing non-http(s) url: {url}", file=sys.stderr)
        return 2

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = _fetch(url)
        body = _to_markdown(raw)
    except Exception as exc:  # noqa: BLE001 — deterministic script surface
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    header = (
        "---\n"
        f"source: {url}\n"
        f"fetched_at: {datetime.now(tz=timezone.utc).isoformat()}\n"
        f"slug: {_slugify(parsed.netloc + parsed.path)}\n"
        "---\n\n"
    )
    out.write_text(header + body, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
