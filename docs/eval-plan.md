# Agent Evaluation Plan

> Mục tiêu: trước khi build observability đầy đủ, **định nghĩa "agent tốt nghĩa là gì"** dưới dạng 1 bộ test chạy được. Log phục vụ eval, eval dẫn dắt cải tiến. Không có rubric thì log chỉ là đống dữ liệu.

## 1. Vì sao eval-first

- Không có rubric = mỗi lần sửa prompt đều dựa cảm tính ("nghe có vẻ tốt hơn").
- Có rubric = đo được regression, biết chắc sửa 1 chỗ không phá 5 chỗ.
- Eval ghi ra traces với label → thành dataset training cho chính nó.

## 2. 5 dimensions đánh giá (áp dụng mọi agent)

| # | Dimension | Cách đo | Trọng số |
|---|-----------|---------|----------|
| D1 | **Correctness** — trả lời đúng domain | golden answer / checker function | 30% |
| D2 | **Persona fidelity** — bám SOUL.md (tone, pacing, correction protocol) | LLM-judge rubric 1–5 | 20% |
| D3 | **Tool use** — gọi đúng skill/tool, không thừa | kiểm tra tool_calls trong trace | 15% |
| D4 | **Memory hygiene** — đọc/ghi MEMORY.md hợp lý | check diff MEMORY.md sau run | 15% |
| D5 | **Safety & cost** — không rò secret, ≤ budget | regex + `total_cost_usd` ngưỡng | 20% |

Score mỗi case ∈ [0, 1]; suite score = trung bình trọng số.

## 3. Cấu trúc test case

```yaml
# evals/english-coach/cases/learn_phrasal_verb.yaml
id: en.learn.phrasal_verb.basic
category: learning.vocabulary
input: "Dạy tôi 1 phrasal verb mới hôm nay"
preconditions:
  memory_seed: |
    ## Vocabulary learned
    - (none)
checks:
  # D1 correctness — hard assertions
  must_contain_any: ["phrasal verb", "meaning", "example"]
  must_not_contain: ["I cannot", "as an AI"]
  # D2 persona — LLM judge
  rubric:
    - "Bot greets in a warm, coaching tone (not robotic)"
    - "Response uses A2–B1 level English (simple sentences)"
    - "Provides 1 example sentence in context, not just definition"
  # D3 tool use
  tools_allowed: [Read, Write, Edit]
  tools_required_any: [Read, Write]  # should read SOUL/MEMORY or write log
  max_tool_calls: 8
  # D4 memory
  memory_must_append: true  # MEMORY.md grew
  memory_must_contain_after: ["phrasal verb"]  # added the verb learned
  # D5 safety/cost
  max_cost_usd: 0.15
  max_duration_s: 60
  forbidden_regex: ["sk-[A-Za-z0-9]{20,}", "xoxb-[A-Za-z0-9-]+"]
```

## 4. Bộ test cơ bản (starter suite)

### 4.1 Suite `english-coach` — 12 cases

| Category | Case id | Mô tả |
|----------|---------|-------|
| smoke | `smoke.hello` | "hi" → bot phản hồi < 10s, có greet |
| smoke | `smoke.who_are_you` | bám Ava persona (A2→C1 coach) |
| learning | `learn.phrasal_verb.basic` | dạy 1 phrasal verb + example |
| learning | `learn.grammar.present_perfect` | giải thích + 2 ví dụ |
| learning | `learn.vocab.business_email` | 5 từ chủ đề công việc |
| correction | `correct.article_misuse` | user viết sai "a/the" → bot chỉnh nhẹ |
| correction | `correct.tense_mix` | user trộn past/present → gợi ý |
| quiz | `quiz.make_5q` | yêu cầu quiz → trigger skill `quiz-maker`, trả gist url hợp lệ |
| flashcard | `flash.make_deck` | yêu cầu deck → trigger `flashcard-deck` |
| memory | `mem.recall_yesterday` | "hôm qua học gì" → đọc MEMORY.md, liệt kê |
| recap | `recap.week` | "tuần này" → trigger `conversation-recap` |
| boundary | `bound.math_question` | hỏi toán → từ chối nhẹ, kéo về tiếng Anh |

### 4.2 Suite `playwright-coach` — 10 cases

| Category | Case id | Mô tả |
|----------|---------|-------|
| smoke | `smoke.hello` | Rook persona |
| learning | `learn.first_test` | viết test `expect(page).toHaveTitle` |
| learning | `learn.locators.role_vs_css` | giải thích khi nào dùng `getByRole` |
| learning | `learn.fixtures.basic` | demo `test.use` fixture |
| debug | `debug.flaky_wait` | fix `waitForTimeout(3000)` → `waitFor` |
| debug | `debug.strict_mode_viol` | 2 elements match selector → sửa |
| ci | `ci.parallel_setup` | config `workers: 4` + shard |
| quiz | `quiz.locators_5q` | trigger `quiz-maker` chủ đề locators |
| memory | `mem.recall_last_spec` | recall spec cuối user viết |
| boundary | `bound.react_question` | hỏi React component → kéo về test |

### 4.3 Cross-agent suite — 5 cases

| Case id | Mô tả |
|---------|-------|
| ops.heartbeat.add | "Mỗi ngày 8h nhắc tôi học" → trigger `heartbeat-ops`, yêu cầu channel, không add nếu bot chưa join |
| ops.heartbeat.channel_validation | cố add vào channel bot chưa ở → refuse với hướng dẫn invite |
| ops.kb.learn | "Học thêm về X" → trigger `kb-research`, add vào knowledge/ |
| ops.empty_input | gửi " " → graceful noop, không crash |
| ops.very_long | 10k ký tự → xử lý hoặc từ chối có context, không timeout |

## 5. Runner architecture

```
coach eval run evals/english-coach/suite.yaml
     │
     ├─► load cases, apply preconditions (seed MEMORY.md, clear .runtime/)
     ├─► for each case:
     │     ├─► POST fake inbound vào router với eval_tag=<suite>.<case_id>
     │     ├─► wait for completion (via trace request_id)
     │     ├─► read trace: tool_calls, usage, cost, assistant_text
     │     ├─► run hard checks (regex, contains, tool list)
     │     ├─► run LLM judge (Haiku) cho rubric items → 1–5 mỗi item
     │     └─► compute case score, write evals/reports/{date}/{suite}.jsonl
     └─► emit summary: per-dim score, regression vs last run, failing cases
```

Key properties:
- **Isolated**: mỗi case chạy trong sandbox session (UUID riêng, cwd tạm).
- **Deterministic seeding**: MEMORY.md/state được reset về `preconditions` trước khi run.
- **Judge model ≠ agent model**: Haiku judge Opus/Sonnet — rẻ + giảm bias self-eval.
- **Trace-native**: mọi case = 1 request_id — dùng luôn tooling ở `observability-plan.md`.

## 6. Report format

```
=== Eval Report: english-coach — 2026-04-16 10:00 ===
Overall: 0.78 (▲ +0.04 vs 2026-04-15)

By dimension:
  D1 Correctness       0.85  ▲
  D2 Persona           0.72  ▼ (-0.03)
  D3 Tool use          0.90  =
  D4 Memory            0.68  ▲
  D5 Safety/Cost       0.95  =

Failing cases (3):
  en.correct.tense_mix   0.40  — rubric: "tone too harsh" 2/5
  en.quiz.make_5q        0.55  — tool: quiz-maker not called
  en.mem.recall_yesterday 0.60 — memory: didn't read MEMORY.md

Cost: $0.84 total, 12 cases, $0.07 avg
Duration: 4m 12s
```

## 7. Iteration loop

```
  1. baseline eval → lưu score vào evals/baseline.json
  2. chạy real → user feedback → tag bad traces (từ observability)
  3. convert "bad" trace → eval case mới (coach eval from-trace <req_id>)
  4. sửa SOUL / skill / prompt
  5. chạy eval → so sánh với baseline
  6. nếu tăng overall + không regress dim nào → commit
  7. nếu regress 1 dim > 5% → revert, nghĩ lại
```

Quy tắc: **không merge thay đổi prompt/skill nếu eval score giảm**.

## 8. Implementation phases

| Phase | Deliverable |
|-------|-------------|
| E1 | Schema YAML test case + loader + 3 smoke cases english-coach |
| E2 | Runner chạy tuần tự, hard checks (contains/regex/tool-list/cost) |
| E3 | LLM judge (Haiku) cho rubric items, score aggregation |
| E4 | Report CLI (`coach eval run`, `coach eval report`, diff vs baseline) |
| E5 | Đủ 12+10+5 cases, CI-ready (exit code 1 nếu regress) |
| E6 | `coach eval from-trace <req_id>` — tự sinh case từ trace đã tag bad |

Tổng ước ~800 LOC, chạy song song với observability-plan (phase E1–E2 phụ thuộc P1 raw trace).

## 9. Thứ tự build — khuyến nghị

```
P1 (raw trace + request_id)        ← tuần này
  └─ E1 (test case schema + 3 smoke)    ← cùng tuần
       └─ P2 (SQLite) + E2 (hard checks)
            └─ P3 + P4 (CLI show) + E3 (LLM judge)
                 └─ E4 (report, baseline diff) ← xài được thật
                      └─ E5 (full suite) + P5 (diff/export/tag)
                           └─ E6 (from-trace)
```

→ Sau ~2 tuần đã có vòng đóng **log → eval → sửa → đo lại**.

## 10. Success criteria

- [ ] 1 lệnh `coach eval run` chạy full suite < 10 phút, chi phí < $2.
- [ ] Mỗi case có score 5 dim + trace_id liên kết `coach trace show`.
- [ ] Sửa SOUL.md → eval báo rõ dim nào tăng/giảm, không đoán.
- [ ] "Bad" trace real-user → 1 lệnh convert thành case regression.
- [ ] CI chặn merge khi overall score giảm > 3% hoặc bất kỳ dim nào giảm > 5%.
