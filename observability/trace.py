"""Trace emitter — captures every request end-to-end.

Three-tier storage:

* Tier 1 (raw): ``.runtime/trace/raw/{YYYY-MM-DD}/{request_id}.jsonl`` —
  one verbatim stream event per line, replay-able.
* Tier 2 (structured): SQLite DB ``.runtime/trace/coach.db`` — one row
  per request, indexed for fast filtering.
* Tier 3 (hot tail): ``.runtime/trace/events/{YYYY-MM-DD}.jsonl`` —
  flatten of all events, convenient for ``tail -f`` / ``jq``.

The emitter is synchronous and best-effort: failures inside an emit
MUST NOT crash the request. All writes are guarded.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from loguru import logger

TRACE_ROOT = Path(".runtime/trace")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    session_id TEXT,
    agent TEXT,
    channel TEXT,
    chat_id TEXT,
    user_id TEXT,
    eval_tag TEXT,
    received_at INTEGER,
    finished_at INTEGER,
    status TEXT,
    model TEXT,
    num_turns INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_creation_tokens INTEGER,
    total_cost_usd REAL,
    user_message TEXT,
    assistant_text TEXT,
    exit_code INTEGER,
    error_tail TEXT,
    label TEXT,
    notes TEXT,
    raw_path TEXT
);
CREATE INDEX IF NOT EXISTS ix_req_agent_time ON requests(agent, received_at);
CREATE INDEX IF NOT EXISTS ix_req_label ON requests(label);
CREATE INDEX IF NOT EXISTS ix_req_eval ON requests(eval_tag);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


class TraceEmitter:
    """Thread-safe, synchronous trace writer.

    One process should hold one emitter. Creation is idempotent and
    cheap; directories/DB are created on first use.
    """

    def __init__(self, root: Path = TRACE_ROOT) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "coach.db"
        self._lock = Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=5)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _raw_path(self, request_id: str) -> Path:
        day_dir = self.root / "raw" / _today()
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir / f"{request_id}.jsonl"

    def _events_path(self) -> Path:
        d = self.root / "events"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{_today()}.jsonl"

    # ------------------------------------------------------------------ API

    def begin_request(
        self,
        *,
        agent: str,
        channel: str = "",
        chat_id: str = "",
        user_id: str = "",
        session_id: str = "",
        user_message: str = "",
        eval_tag: str | None = None,
        model: str | None = None,
    ) -> str:
        request_id = uuid.uuid4().hex
        raw_path = str(self._raw_path(request_id))
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO requests (request_id, session_id, agent, channel, "
                    "chat_id, user_id, eval_tag, received_at, status, model, "
                    "user_message, raw_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        request_id,
                        session_id,
                        agent,
                        channel,
                        chat_id,
                        user_id,
                        eval_tag,
                        _now_ms(),
                        "running",
                        model,
                        user_message,
                        raw_path,
                    ),
                )
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning("trace begin_request failed: {}", exc)
        self.event(
            request_id,
            "request_begin",
            {
                "agent": agent,
                "channel": channel,
                "chat_id": chat_id,
                "session_id": session_id,
                "eval_tag": eval_tag,
            },
        )
        return request_id

    def event(self, request_id: str, kind: str, payload: Any) -> None:
        record = {
            "ts": _now_ms(),
            "request_id": request_id,
            "kind": kind,
            "payload": payload,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._raw_path(request_id).open("a", encoding="utf-8") as f:
                f.write(line)
            with self._events_path().open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception as exc:  # noqa: BLE001
            logger.warning("trace event {} failed: {}", kind, exc)

    def finish_request(
        self,
        request_id: str,
        *,
        status: str,
        assistant_text: str = "",
        usage: dict[str, Any] | None = None,
        cost_usd: float | None = None,
        num_turns: int | None = None,
        exit_code: int | None = None,
        error_tail: str | None = None,
    ) -> None:
        usage = usage or {}
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE requests SET finished_at=?, status=?, assistant_text=?, "
                    "input_tokens=COALESCE(?, input_tokens), "
                    "output_tokens=COALESCE(?, output_tokens), "
                    "cache_read_tokens=COALESCE(?, cache_read_tokens), "
                    "cache_creation_tokens=COALESCE(?, cache_creation_tokens), "
                    "total_cost_usd=COALESCE(?, total_cost_usd), "
                    "num_turns=COALESCE(?, num_turns), "
                    "exit_code=?, error_tail=? WHERE request_id=?",
                    (
                        _now_ms(),
                        status,
                        assistant_text,
                        usage.get("input_tokens"),
                        usage.get("output_tokens"),
                        usage.get("cache_read_input_tokens"),
                        usage.get("cache_creation_input_tokens"),
                        cost_usd,
                        num_turns,
                        exit_code,
                        (error_tail or "")[:2000],
                        request_id,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("trace finish_request failed: {}", exc)
        self.event(
            request_id,
            "request_finish",
            {
                "status": status,
                "assistant_chars": len(assistant_text),
                "cost_usd": cost_usd,
                "usage": usage,
                "exit_code": exit_code,
            },
        )

    def update_usage(
        self,
        request_id: str,
        *,
        usage: dict[str, Any] | None = None,
        cost_usd: float | None = None,
        num_turns: int | None = None,
    ) -> None:
        usage = usage or {}
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE requests SET input_tokens=COALESCE(?, input_tokens), "
                    "output_tokens=COALESCE(?, output_tokens), "
                    "cache_read_tokens=COALESCE(?, cache_read_tokens), "
                    "cache_creation_tokens=COALESCE(?, cache_creation_tokens), "
                    "total_cost_usd=COALESCE(?, total_cost_usd), "
                    "num_turns=COALESCE(?, num_turns) WHERE request_id=?",
                    (
                        usage.get("input_tokens"),
                        usage.get("output_tokens"),
                        usage.get("cache_read_input_tokens"),
                        usage.get("cache_creation_input_tokens"),
                        cost_usd,
                        num_turns,
                        request_id,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("trace update_usage failed: {}", exc)

    def tag(self, request_id: str, label: str | None, notes: str | None = None) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE requests SET label=?, notes=? WHERE request_id=?",
                    (label, notes, request_id),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("trace tag failed: {}", exc)

    # ------------------------------------------------------------------ Read API

    def list_requests(
        self,
        *,
        agent: str | None = None,
        since_ms: int | None = None,
        status: str | None = None,
        eval_tag: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        q = "SELECT * FROM requests WHERE 1=1"
        args: list[Any] = []
        if agent:
            q += " AND agent=?"
            args.append(agent)
        if since_ms is not None:
            q += " AND received_at>=?"
            args.append(since_ms)
        if status:
            q += " AND status=?"
            args.append(status)
        if eval_tag:
            q += " AND eval_tag=?"
            args.append(eval_tag)
        q += " ORDER BY received_at DESC LIMIT ?"
        args.append(limit)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM requests WHERE request_id=?", (request_id,)
            ).fetchone()
        return dict(row) if row else None

    def read_raw(self, request_id: str) -> list[dict[str, Any]]:
        req = self.get_request(request_id)
        if not req or not req.get("raw_path"):
            return []
        path = Path(req["raw_path"])
        if not path.exists():
            return []
        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events


_emitter: TraceEmitter | None = None


def get_emitter(root: Path | None = None) -> TraceEmitter:
    """Return (and lazily create) the process-wide emitter."""
    global _emitter
    if _emitter is None:
        _emitter = TraceEmitter(root or TRACE_ROOT)
    return _emitter
