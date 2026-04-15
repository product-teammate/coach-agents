"""``coach eval run <suite.yaml>`` — run a YAML suite of agent test cases.

Phase E1/E2: hard checks only (contains/regex/cost/duration). No LLM
judge yet — that is E3. A case passes when all hard checks pass.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from pathlib import Path

import typer
import yaml

from brains._base import BrainInvocation
from brains.advise_mode import build as build_advise_prompt
from brains.claude_code.adapter import ClaudeCodeBrain
from observability import get_emitter
from runtime.permissions import merge_tools

eval_app = typer.Typer(help="Run agent evaluation suites.")


def _load_agent(agent_dir: Path) -> dict:
    return yaml.safe_load((agent_dir / "agent.yaml").read_text())


def _run_one_case(
    agent_dir: Path, case: dict, eval_tag: str
) -> dict:
    """Invoke brain for a single case; return result dict with metrics."""
    cfg = _load_agent(agent_dir)
    agent_id = cfg.get("agent", {}).get("id") or agent_dir.name
    brain_cfg = cfg.get("brain", {})

    emitter = get_emitter()
    session_tag = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    request_id = emitter.begin_request(
        agent=agent_id,
        channel="eval",
        chat_id=case["id"],
        session_id=f"eval:{session_tag}",
        user_message=case["input"],
        eval_tag=eval_tag,
        model=brain_cfg.get("model"),
    )

    inv = BrainInvocation(
        agent_dir=agent_dir,
        user_message=case["input"],
        session_id=f"eval:{session_tag}",
        allowed_tools=merge_tools(
            brain_cfg.get("allowed_tools") or [], cfg.get("skills") or []
        ),
        model=brain_cfg.get("model"),
        timeout_s=int(case.get("timeout_s") or brain_cfg.get("timeout_s") or 120),
        permission_mode=brain_cfg.get("permission_mode") or "acceptEdits",
        request_id=request_id,
        append_system_prompt=build_advise_prompt(
            bool(brain_cfg.get("advise_mode"))
        ),
    )

    brain = ClaudeCodeBrain()
    started = time.time()

    async def _run() -> tuple[str, str, str | None]:
        buf: list[str] = []
        status = "ok"
        err = None
        try:
            async for chunk in brain.invoke(inv):
                buf.append(chunk)
        except Exception as exc:  # noqa: BLE001
            status = "error"
            err = repr(exc)
        combined = "".join(buf).strip()
        if not combined and status == "ok":
            status = "empty"
        emitter.finish_request(
            request_id,
            status=status,
            assistant_text=combined,
            error_tail=err,
        )
        return combined, status, err

    text, status, err = asyncio.run(_run())
    duration = time.time() - started

    # Re-read request to get cost/tokens populated by adapter
    req = emitter.get_request(request_id) or {}

    # Hard checks
    checks = case.get("checks") or {}
    failures: list[str] = []

    if status == "error":
        failures.append(f"brain error: {err}")
    if status == "empty":
        failures.append("empty response")

    needles_any = checks.get("must_contain_any") or []
    if needles_any:
        lowered = text.lower()
        if not any(n.lower() in lowered for n in needles_any):
            failures.append(
                f"none of must_contain_any matched: {needles_any}"
            )

    for needle in checks.get("must_contain_all") or []:
        if needle.lower() not in text.lower():
            failures.append(f"missing must_contain_all: {needle!r}")

    for needle in checks.get("must_not_contain") or []:
        if needle.lower() in text.lower():
            failures.append(f"forbidden phrase present: {needle!r}")

    for pat in checks.get("forbidden_regex") or []:
        if re.search(pat, text):
            failures.append(f"forbidden regex matched: {pat!r}")

    max_cost = checks.get("max_cost_usd")
    if max_cost is not None and (req.get("total_cost_usd") or 0) > max_cost:
        failures.append(
            f"cost {req.get('total_cost_usd')} > max_cost_usd {max_cost}"
        )

    max_dur = checks.get("max_duration_s")
    if max_dur is not None and duration > max_dur:
        failures.append(f"duration {duration:.1f}s > max_duration_s {max_dur}")

    min_chars = checks.get("min_assistant_chars")
    if min_chars is not None and len(text) < min_chars:
        failures.append(f"assistant chars {len(text)} < min {min_chars}")

    return {
        "case_id": case["id"],
        "request_id": request_id,
        "status": status,
        "passed": not failures,
        "failures": failures,
        "duration_s": round(duration, 2),
        "cost_usd": req.get("total_cost_usd"),
        "assistant_chars": len(text),
    }


@eval_app.command("run")
def run(
    suite: Path = typer.Argument(..., help="Suite YAML or directory"),
    only: str | None = typer.Option(None, "--only", help="Run only case id(s), comma-separated"),
) -> None:
    """Run a suite file. Prints a summary and exits non-zero if any case fails."""
    suite_path = Path(suite)
    if suite_path.is_dir():
        candidate = suite_path / "suite.yaml"
        if not candidate.exists():
            typer.echo(f"no suite.yaml in {suite_path}")
            raise typer.Exit(2)
        suite_path = candidate

    spec = yaml.safe_load(suite_path.read_text())
    agent = spec.get("agent")
    if not agent:
        typer.echo("suite missing 'agent' field")
        raise typer.Exit(2)
    agent_dir = Path("agents") / agent
    if not agent_dir.exists():
        typer.echo(f"agent dir not found: {agent_dir}")
        raise typer.Exit(2)

    cases = spec.get("cases") or []
    if only:
        wanted = {x.strip() for x in only.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if not cases:
        typer.echo("no cases to run")
        raise typer.Exit(2)

    eval_tag = f"{suite_path.stem}:{time.strftime('%Y%m%d-%H%M%S')}"
    typer.echo(f"▶ running {len(cases)} case(s) on agent={agent} tag={eval_tag}")

    results = []
    for idx, case in enumerate(cases, 1):
        typer.echo(f"  [{idx}/{len(cases)}] {case['id']}…")
        r = _run_one_case(agent_dir, case, eval_tag)
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL"
        typer.echo(
            f"      {mark}  req={r['request_id'][:12]} "
            f"dur={r['duration_s']}s cost=${r['cost_usd'] or 0:.4f}"
        )
        for f in r["failures"]:
            typer.echo(f"        - {f}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    total_cost = sum((r["cost_usd"] or 0) for r in results)
    typer.echo(
        f"\n=== {passed}/{total} passed  cost=${total_cost:.4f}  tag={eval_tag} ==="
    )
    typer.echo("Use `coach trace show <req_id>` to inspect any case.")

    raise typer.Exit(0 if passed == total else 1)
