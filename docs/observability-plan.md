# Observability & Trace Plan

> Mục tiêu: capture toàn bộ vòng đời mỗi request (inbound → brain → tools → outbound), gán **request_id** để query lại dễ dàng, hỗ trợ review-loop nhiều lần tinh chỉnh prompt/skill cho đến khi đạt kết quả hoàn hảo.

## 1. Scope — cần capture gì

| Giai đoạn | Dữ liệu |
|-----------|---------|
| Inbound | channel, chat_id, user_id, agent, raw text, received_at |
| Routing | request_id, session_id (UUIDv5), permission_mode, allowed_tools, model |
| Brain spawn | full CLI argv, cwd, subset env, PID, spawn_at |
| Stream events | mọi event claude stream-json: `system`, `assistant`, `stream_event`, `tool_use`, `tool_result`, `user`, `result`, `error` |
| Tool calls | name, params (truncated), result snippet, duration_ms |
| Cost/usage | `result.usage.{input,output,cache_creation,cache_read}_tokens`, `total_cost_usd`, `duration_ms`, `num_turns` |
| Outbound | channel chunks sent, total_chars, posted_at |
| Termination | exit_code, stderr_tail, exception |

## 2. Correlation model

- **request_id** = UUIDv4 sinh ra tại `router._handle` inbound, là khoá chính.
- **session_id** = UUIDv5 deterministic (đã có) — gộp các request trong cùng thread.
- **trace_id** = tuỳ chọn, cho workflow đa-request (heartbeat → chat → tool chain).
- Propagation:
  - `loguru.contextualize(request_id=...)` để mọi log line tự động kèm.
  - Truyền qua subprocess env `COACH_REQUEST_ID` để child tool có thể log kèm.
  - Mọi record trong DB/JSONL đều có `request_id`.

## 3. Storage — 3 tier

### Tier 1: Raw stream (replay source of truth)
- Path: `.runtime/trace/raw/{YYYY-MM-DD}/{request_id}.jsonl`
- Mỗi dòng = 1 event claude stream-json, verbatim (không lossy).
- Dùng để **replay/diff/re-parse** khi đổi adapter mà không cần chạy lại LLM.

### Tier 2: Structured SQLite (query layer)
- Path: `.runtime/trace/coach.db` (WAL mode, single writer task).
- Schema:
  ```sql
  CREATE TABLE requests (
    request_id TEXT PRIMARY KEY,
    session_id TEXT,
    agent TEXT, channel TEXT, chat_id TEXT, user_id TEXT,
    received_at INTEGER, finished_at INTEGER,
    status TEXT,                 -- ok | empty | error | timeout
    model TEXT, num_turns INTEGER,
    input_tokens INTEGER, output_tokens INTEGER,
    cache_read_tokens INTEGER, cache_creation_tokens INTEGER,
    total_cost_usd REAL,
    user_message TEXT, assistant_text TEXT,
    exit_code INTEGER, error_tail TEXT,
    label TEXT,                  -- good|bad|needs-review|null
    notes TEXT
  );
  CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT, ts INTEGER, kind TEXT, payload_json TEXT,
    FOREIGN KEY(request_id) REFERENCES requests(request_id)
  );
  CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT, tool TEXT, started_at INTEGER, duration_ms INTEGER,
    params_excerpt TEXT, result_excerpt TEXT, status TEXT,
    FOREIGN KEY(request_id) REFERENCES requests(request_id)
  );
  CREATE INDEX ix_req_agent_time ON requests(agent, received_at);
  CREATE INDEX ix_req_label ON requests(label);
  CREATE INDEX ix_ev_req ON events(request_id);
  CREATE INDEX ix_tool_req ON tool_calls(request_id);
  ```

### Tier 3: Hot JSONL (daily tail)
- Path: `.runtime/trace/events/{YYYY-MM-DD}.jsonl` — tất cả event flatten, thuận tiện `grep`/`jq`/`tail -f`.

## 4. Component design

```
 Slack/Tele ──► Router ──► Brain(adapter) ──► claude CLI
                  │             │                   │
                  ▼             ▼                   ▼
               TraceEmitter (async queue, single writer task)
                  │
          ┌───────┼────────┐
          ▼       ▼        ▼
        raw/  SQLite   events/ JSONL
```

- `observability/trace.py` — `TraceEmitter`:
  - `begin_request(**fields) -> request_id`
  - `event(request_id, kind, payload)` — raw stream event passthrough
  - `tool_call(request_id, tool, params, result, status, duration)`
  - `finish_request(request_id, status, usage, cost, assistant_text, exit_code, stderr)`
- Writer chạy async task duy nhất, nhận qua `asyncio.Queue`, flush batch 100 hoặc 500ms.
- Mất dữ liệu an toàn: nếu queue đầy → log WARNING + drop event (request record vẫn ghi).

## 5. CLI — `coach trace *`

| Lệnh | Mục đích |
|------|----------|
| `coach trace list [--agent X] [--since 1h] [--status empty]` | bảng recent requests |
| `coach trace show <request_id>` | timeline đẹp: inbound → tool calls → output |
| `coach trace replay <request_id>` | dump raw JSONL (để re-parse adapter) |
| `coach trace diff <req_a> <req_b>` | so sánh 2 lần chạy cùng prompt |
| `coach trace cost [--since 24h] [--group-by agent]` | rollup token/$ |
| `coach trace tag <request_id> --label good\|bad --note "..."` | gán nhãn review |
| `coach trace export --label bad --since 7d > eval.jsonl` | xuất dataset để eval/fine-tune prompt |
| `coach trace prune --older-than 30d` | dọn Tier 1/3, giữ Tier 2 |

## 6. Review-loop workflow (chốt điểm mấu đề user hỏi)

1. Chạy prompt thật → sinh `request_id`.
2. `coach trace show <req_id>` đọc lại: chuỗi tool call, output, cost.
3. Không ưng → `coach trace tag <req_id> --label bad --note "thiếu bước quiz"`.
4. Chỉnh SOUL.md / skill / prompt → chạy lại → có `req_id_2`.
5. `coach trace diff req_id req_id_2` → thấy đúng khác biệt.
6. Lặp đến khi ưng → `--label good`.
7. Cuối tuần `coach trace export --label bad` → bộ test-case regression.

## 7. Implementation plan — 5 phase

| Phase | Deliverable | LOC ước tính |
|-------|-------------|--------------|
| P1 | `TraceEmitter` + Tier 1 raw JSONL + `request_id` propagation | ~150 |
| P2 | SQLite schema + async writer + `requests` + `events` | ~250 |
| P3 | Parse tool_use/tool_result vào `tool_calls`, usage/cost parse `result` | ~150 |
| P4 | CLI `coach trace {list,show,cost,tag}` (rich table) | ~200 |
| P5 | `diff`, `export`, `replay`, `prune` + retention job | ~200 |

Tổng ~950 LOC, test kèm mỗi phase, mỗi phase 1 commit + push.

## 8. Tradeoffs & rủi ro

- **SQLite đủ**: single-host, 1 writer. Nếu sau này multi-node → PostgreSQL (schema giữ nguyên).
- **Không OTEL ngay**: custom đơn giản hơn, dễ debug. Sau thêm exporter OTEL → Honeycomb/Grafana.
- **PII**: user_message nguyên văn được lưu → DB local-only, không sync cloud. `coach trace export` mặc định redact, cần `--include-raw` mới giữ.
- **Disk**: Tier 1 raw có thể ~50–200KB/request. `prune --older-than 30d` mặc định; archive thành `.tar.zst` nếu cần lâu.
- **Concurrent writes**: WAL + 1 writer task loại trừ lock contention.
- **Failure isolation**: lỗi trace KHÔNG được crash request; emitter bọc try/except, log error.

## 9. Monitoring dashboard (optional, phase 6)

- Trang HTML tĩnh sinh từ SQLite bằng `jinja2` → mở bằng `coach trace ui`.
- Bảng requests, click vào → timeline + stream raw + tool calls.
- Filter theo label, agent, cost, tokens.
- Không cần web server — file://.

## 10. Success criteria

- [ ] Mọi request Slack/Tele đều tạo 1 row `requests` + ≥1 `events`.
- [ ] `coach trace show <id>` render được timeline từ inbound → outbound.
- [ ] Reproduce được 1 session cũ: `coach trace replay <id>` → feed lại parser → cùng output.
- [ ] Query "7 ngày gần nhất, agent english-coach, tool_calls > 5" trả kết quả <100ms.
- [ ] Workflow review-loop (tag bad → fix → tag good → diff) làm được end-to-end không cần tool ngoài.
