"""Shared core for knowledge ingestion.

Both ``coach learn`` (CLI) and the heartbeat onboarding consumer call
into this module so the prompt construction and brain invocation live in
exactly one place.

Four ingestion modes are supported:

- ``auto`` — Claude plans topics from SOUL + USER, fetches all.
- ``targeted`` — one topic string.
- ``batch`` — list of URLs.
- ``dry_run`` — same as ``auto`` but asks Claude to only print the plan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterable, Literal

from brains._base import Brain, BrainInvocation
from brains.claude_code.adapter import ClaudeCodeBrain
from coach_cli.commands._knowledge_index import regenerate_index
from runtime.loader import LoadedAgent, load_agent
from runtime.permissions import merge_tools


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"


Mode = Literal["auto", "targeted", "batch", "dry_run"]


@dataclass(frozen=True)
class LearnRequest:
    """Parameters for a single ``coach learn`` invocation."""

    agent_id: str
    mode: Mode
    topic: str | None = None
    urls: list[str] | None = None
    max_files: int | None = None


# Tools Claude needs for knowledge ingestion. Merged with agent+skill
# declarations so the agent's own whitelist always wins conflicts.
_LEARN_TOOLS: tuple[str, ...] = (
    "Read",
    "Write",
    "Edit",
    "WebFetch",
    "Bash",
    "Grep",
    "Glob",
)


def resolve_agent(agent_id: str) -> LoadedAgent:
    """Load + validate an agent from ``agents/<id>/``."""
    agent_dir = AGENTS_DIR / agent_id
    if not agent_dir.exists():
        raise FileNotFoundError(f"no such agent: {agent_dir}")
    return load_agent(agent_dir)


def build_prompt(agent: LoadedAgent, req: LearnRequest) -> str:
    """Construct the one-shot prompt for Claude based on mode."""
    name = agent.config.get("agent", {}).get("name") or agent.agent_id
    max_clause = ""
    if req.max_files is not None:
        max_clause = f"\n\nHard cap: fetch at most {req.max_files} files in this run."

    if req.mode == "auto" or req.mode == "dry_run":
        prompt = (
            f"You are the {name} coach performing a one-time knowledge base pre-load.\n\n"
            "Read SOUL.md and USER.md carefully. Based on the coach's domain, "
            "learning arc, and (if filled) the learner's current level and goals, "
            "list 5-10 foundational knowledge topics this coach needs in its "
            "knowledge base to operate effectively.\n\n"
            "For each topic:\n"
            "1. Choose an authoritative source from skills/kb-research/sources.yaml "
            "allowlist (or explain why another source is needed).\n"
            "2. Use WebFetch to retrieve content.\n"
            "3. Convert to clean markdown.\n"
            "4. Save to knowledge/<slug>.md with YAML frontmatter:\n"
            "   ---\n"
            "   topic: <topic>\n"
            "   source: <url>\n"
            "   fetched_at: <ISO 8601>\n"
            "   tags: [<tag1>, <tag2>]\n"
            "   ---\n"
            "5. After all topics fetched, create/update knowledge/INDEX.md with one "
            "line per file:\n"
            "   - `<slug>.md` - <one-sentence summary>\n\n"
            "Constraints:\n"
            "- Stay within the sources.yaml allowlist unless no authoritative "
            "alternative exists.\n"
            "- Max 10 files in one run.\n"
            "- If a fetch fails, log and skip - don't abort the whole batch.\n"
            "- Each file should be 500-3000 words (not too thin, not a full book).\n"
            "- De-duplicate - don't fetch two pages on the same concept.\n"
            "- Deterministic slugs: lowercase, kebab-case, no timestamps in filename.\n\n"
            "Return a summary of what was fetched, what was skipped, and any errors."
        )
        if req.mode == "dry_run":
            prompt += (
                "\n\nOnly list the topics you would research and the URLs you would "
                "fetch. Do NOT actually fetch or write any files."
            )
        return prompt + max_clause

    if req.mode == "targeted":
        topic = (req.topic or "").strip()
        if not topic:
            raise ValueError("targeted mode requires a topic string")
        return (
            f"You are the {name} coach adding one topic to the knowledge base: "
            f'"{topic}"\n\n'
            "Use WebFetch to retrieve content from authoritative sources (prefer "
            "those listed in skills/kb-research/sources.yaml). Clean + save to "
            "knowledge/<slug>.md with the standard frontmatter (topic, source, "
            "fetched_at, tags). Update knowledge/INDEX.md.\n\n"
            "If the topic is broad, split into 2-3 focused sub-files rather than "
            "one mega-file."
        ) + max_clause

    if req.mode == "batch":
        urls = req.urls or []
        if not urls:
            raise ValueError("batch mode requires at least one URL")
        url_block = "\n".join(urls)
        return (
            f"You are the {name} coach ingesting a batch of URLs into the "
            "knowledge base.\n\n"
            "URLs (one per line):\n"
            f"{url_block}\n\n"
            "For each URL: fetch via WebFetch, clean, save to knowledge/<slug>.md "
            "with standard frontmatter (source = the URL). Update knowledge/"
            "INDEX.md. Skip URLs outside the sources.yaml allowlist unless the "
            'batch file explicitly includes a "# override" comment line above the URL.'
        ) + max_clause

    raise ValueError(f"unknown mode: {req.mode}")


def parse_batch_file(path: Path) -> list[str]:
    """Read a URL-per-line file. Blank lines kept out; comments preserved.

    ``# override`` comment lines are preserved verbatim so Claude can see
    the override marker next to the URL that follows.
    """
    raw = path.read_text(encoding="utf-8")
    out: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        out.append(stripped)
    return out


def _build_invocation(agent: LoadedAgent, prompt: str) -> BrainInvocation:
    brain_cfg = agent.config.get("brain", {})
    agent_tools = list(brain_cfg.get("allowed_tools") or [])
    # Guarantee the learn toolset is available even if the agent's base
    # whitelist is narrow. Skill-level tools also merged in as usual.
    merged = merge_tools(agent_tools + list(_LEARN_TOOLS), agent.skills)
    session_id = f"learn:{agent.agent_id}:{int(time.time())}"
    return BrainInvocation(
        agent_dir=agent.directory,
        user_message=prompt,
        session_id=session_id,
        allowed_tools=merged,
        model=brain_cfg.get("model"),
        timeout_s=600,
        permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
    )


async def stream_learn(
    req: LearnRequest, brain: Brain | None = None
) -> AsyncIterator[str]:
    """Yield chunks from Claude as it runs the ingestion plan.

    The caller is responsible for printing/accumulating chunks. After the
    stream completes, call :func:`finalize_learn` to regenerate INDEX.md.
    """
    agent = resolve_agent(req.agent_id)
    prompt = build_prompt(agent, req)
    inv = _build_invocation(agent, prompt)
    brain = brain or ClaudeCodeBrain()
    async for chunk in brain.invoke(inv):
        yield chunk


def finalize_learn(agent_id: str) -> Path | None:
    """Regenerate ``knowledge/INDEX.md`` for the agent.

    Returns the written index path, or ``None`` if the agent has no
    knowledge directory configured.
    """
    try:
        agent = resolve_agent(agent_id)
    except (FileNotFoundError, ValueError):
        return None
    knowledge_rel = (agent.config.get("knowledge") or {}).get("dir") or "knowledge/"
    knowledge_dir = agent.directory / knowledge_rel
    return regenerate_index(knowledge_dir)


def list_knowledge_files(agent_id: str) -> list[Path]:
    """Return absolute paths of ``knowledge/*.md`` files (excluding INDEX)."""
    try:
        agent = resolve_agent(agent_id)
    except (FileNotFoundError, ValueError):
        return []
    knowledge_rel = (agent.config.get("knowledge") or {}).get("dir") or "knowledge/"
    knowledge_dir = agent.directory / knowledge_rel
    if not knowledge_dir.exists():
        return []
    out: list[Path] = []
    for child in sorted(knowledge_dir.iterdir()):
        if child.is_file() and child.suffix == ".md" and child.name != "INDEX.md":
            out.append(child)
    return out


def format_file_summary(paths: Iterable[Path]) -> str:
    """Render a short human-readable list of files + byte sizes."""
    rows: list[str] = []
    for p in paths:
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        rows.append(f"  {p.name:<50} {size:>8} bytes")
    if not rows:
        return "  (no knowledge files)"
    return "\n".join(rows)
