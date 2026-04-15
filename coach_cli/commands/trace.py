"""``coach trace [list|show|tag|cost]`` — read traces from the DB."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Optional

import typer

from observability import get_emitter

trace_app = typer.Typer(help="Inspect request traces.")


def _fmt_ts(ms: Optional[int]) -> str:
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M:%S")


def _parse_since(since: str) -> int:
    m = re.fullmatch(r"(\d+)([smhd])", since)
    if not m:
        raise typer.BadParameter("use formats like 30m, 2h, 7d")
    n, unit = int(m.group(1)), m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return int((time.time() - n * mult) * 1000)


@trace_app.command("list")
def list_cmd(
    agent: Optional[str] = typer.Option(None, "--agent", "-a"),
    since: Optional[str] = typer.Option(None, "--since", help="e.g. 1h, 30m, 7d"),
    status: Optional[str] = typer.Option(None, "--status"),
    eval_tag: Optional[str] = typer.Option(None, "--eval-tag"),
    limit: int = typer.Option(30, "--limit", "-n"),
) -> None:
    """List recent requests."""
    em = get_emitter()
    since_ms = _parse_since(since) if since else None
    rows = em.list_requests(
        agent=agent,
        since_ms=since_ms,
        status=status,
        eval_tag=eval_tag,
        limit=limit,
    )
    if not rows:
        typer.echo("(no requests)")
        return
    typer.echo(
        f"{'time':<15} {'agent':<18} {'status':<8} {'cost$':<7} {'chars':<6} {'req_id':<16} msg"
    )
    for r in rows:
        cost = r.get("total_cost_usd")
        cost_s = f"{cost:.4f}" if cost else "-"
        chars = len(r.get("assistant_text") or "")
        msg = (r.get("user_message") or "").replace("\n", " ")[:40]
        typer.echo(
            f"{_fmt_ts(r.get('received_at')):<15} "
            f"{(r.get('agent') or '')[:18]:<18} "
            f"{(r.get('status') or '')[:8]:<8} "
            f"{cost_s:<7} "
            f"{chars:<6} "
            f"{r['request_id'][:16]:<16} "
            f"{msg}"
        )


@trace_app.command("show")
def show_cmd(
    request_id: str = typer.Argument(...),
    raw: bool = typer.Option(False, "--raw", help="dump raw stream events"),
) -> None:
    """Show a request's timeline."""
    em = get_emitter()
    req = em.get_request(request_id)
    if not req:
        # prefix match
        rows = em.list_requests(limit=200)
        matches = [r for r in rows if r["request_id"].startswith(request_id)]
        if len(matches) == 1:
            req = matches[0]
        elif len(matches) > 1:
            typer.echo(f"ambiguous prefix, {len(matches)} matches")
            raise typer.Exit(2)
        else:
            typer.echo("not found")
            raise typer.Exit(1)

    typer.echo(f"request_id : {req['request_id']}")
    typer.echo(f"agent      : {req.get('agent')}")
    typer.echo(f"channel    : {req.get('channel')}  chat_id={req.get('chat_id')}")
    typer.echo(f"session    : {req.get('session_id')}")
    typer.echo(f"received   : {_fmt_ts(req.get('received_at'))}")
    typer.echo(f"finished   : {_fmt_ts(req.get('finished_at'))}")
    typer.echo(f"status     : {req.get('status')}")
    typer.echo(f"eval_tag   : {req.get('eval_tag') or '-'}")
    typer.echo(f"label      : {req.get('label') or '-'}")
    typer.echo(
        f"tokens     : in={req.get('input_tokens')} "
        f"out={req.get('output_tokens')} "
        f"cache_r={req.get('cache_read_tokens')} "
        f"cache_c={req.get('cache_creation_tokens')}"
    )
    typer.echo(f"cost_usd   : {req.get('total_cost_usd')}")
    typer.echo(f"exit_code  : {req.get('exit_code')}")
    typer.echo("─── user ───")
    typer.echo(req.get("user_message") or "")
    typer.echo("─── assistant ───")
    typer.echo(req.get("assistant_text") or "(empty)")
    if req.get("error_tail"):
        typer.echo("─── error ───")
        typer.echo(req["error_tail"])

    events = em.read_raw(req["request_id"])
    typer.echo(f"─── events ({len(events)}) ───")
    for ev in events:
        if raw:
            typer.echo(json.dumps(ev, ensure_ascii=False))
            continue
        kind = ev.get("kind", "?")
        payload = ev.get("payload") or {}
        if kind.startswith("stream:"):
            inner_type = payload.get("type") or "?"
            brief = ""
            if inner_type == "assistant":
                blocks = (payload.get("message") or {}).get("content") or []
                parts = []
                for b in blocks:
                    t = b.get("type")
                    if t == "text":
                        parts.append(f"text({len(b.get('text') or '')}c)")
                    elif t == "tool_use":
                        parts.append(f"tool_use({b.get('name')})")
                    else:
                        parts.append(t or "?")
                brief = " ".join(parts)
            elif inner_type == "result":
                brief = (
                    f"subtype={payload.get('subtype')} "
                    f"turns={payload.get('num_turns')} "
                    f"${payload.get('total_cost_usd')}"
                )
            typer.echo(f"  {_fmt_ts(ev.get('ts'))}  stream:{inner_type:<12} {brief}")
        else:
            typer.echo(f"  {_fmt_ts(ev.get('ts'))}  {kind}")


@trace_app.command("tag")
def tag_cmd(
    request_id: str = typer.Argument(...),
    label: str = typer.Option(..., "--label", help="good|bad|needs-review"),
    note: str = typer.Option("", "--note"),
) -> None:
    em = get_emitter()
    em.tag(request_id, label, note or None)
    typer.echo(f"tagged {request_id} -> {label}")


@trace_app.command("cost")
def cost_cmd(
    since: str = typer.Option("24h", "--since"),
) -> None:
    em = get_emitter()
    since_ms = _parse_since(since)
    rows = em.list_requests(since_ms=since_ms, limit=10_000)
    total = sum((r.get("total_cost_usd") or 0) for r in rows)
    by_agent: dict[str, tuple[int, float]] = {}
    for r in rows:
        a = r.get("agent") or "?"
        c = r.get("total_cost_usd") or 0
        n, s = by_agent.get(a, (0, 0.0))
        by_agent[a] = (n + 1, s + c)
    typer.echo(f"since={since}  requests={len(rows)}  total=${total:.4f}")
    for a, (n, s) in sorted(by_agent.items(), key=lambda x: -x[1][1]):
        typer.echo(f"  {a:<20} n={n:<5} ${s:.4f}")
