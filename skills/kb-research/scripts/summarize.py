"""Build a cross-source summary stub from previously fetched knowledge files.

Usage:
    python summarize.py <path1.md> [<path2.md> ...]

This script is intentionally lightweight — it lays down a template for Claude
Code to fill in during the next turn. It does NOT call any LLM directly; the
real summarization is delegated back to the brain by the surrounding playbook.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _extract_source(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "unknown source"
    for line in m.group(1).splitlines():
        if line.startswith("source:"):
            return line.split(":", 1)[1].strip()
    return "unknown source"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    paths = [Path(p) for p in argv[1:]]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"missing files: {missing}", file=sys.stderr)
        return 1

    # Derive output path: knowledge/_summaries/<first-file-stem>.md
    first = paths[0]
    summaries_dir = first.parent / "_summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    out = summaries_dir / f"{first.stem.split('-')[0]}-summary.md"

    lines = [
        "---",
        f"generated_at: {datetime.now(tz=timezone.utc).isoformat()}",
        f"sources: {len(paths)}",
        "---",
        "",
        "# Summary (TODO — fill in from sources below)",
        "",
        "## Sources",
    ]
    for p in paths:
        src = _extract_source(p.read_text(encoding="utf-8"))
        lines.append(f"- [{p.name}]({p.name}) — {src}")
    lines += [
        "",
        "## Key points",
        "- TODO: the brain should fill this in next turn.",
        "",
        "## Open questions",
        "- TODO",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
