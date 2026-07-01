---
phase: 2
slug: memory
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-29
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 02-RESEARCH.md `## Validation Architecture`. The Per-Task
> Verification Map is keyed by requirement; task IDs are assigned once PLAN.md
> files exist (then promote `status: ready` / `nyquist_compliant: true`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — `python -m unittest discover -s tests -v` |
| **Quick run command** | `cd backend && python -m unittest discover -s tests -v` |
| **Full suite command** | Same (all test modules; existing ~58 tests are the regression gate) |
| **Estimated runtime** | ~3–10 seconds (no live DB; checkpointer/store mocked; round-trip smoke runs separately) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m unittest discover -s tests -v` (existing tests must remain green — no regression)
- **After every plan wave:** Full suite + the manual cross-session persistence round-trip (see Manual-Only Verifications)
- **Before `/gsd-verify-work`:** Full suite green AND all 5 Roadmap success criteria observably TRUE in the live UI
- **Max feedback latency:** ~10 seconds for the unit suite; cross-session round-trip gated by live Supabase env

---

## Per-Task Verification Map

> Requirement-level seed. Task IDs (e.g. `02-01-01`) and Threat Refs are bound to
> concrete `<task>` blocks once the planner emits PLAN.md, then this table is
> promoted to task granularity.

| Req | Behavior | Test Type | Automated Command | File Exists |
|-----|----------|-----------|-------------------|-------------|
| MEM-01 | `X-Session-Id` header read from request and used as `thread_id` | unit | `python -m unittest tests.test_api.MemorySessionTests.test_session_id_from_header -v` | ❌ W0 |
| MEM-02 | Conversation history restores on new request with same session_id | integration (mocked checkpointer) | `python -m unittest tests.test_memory.CheckpointRestoreTests -v` | ❌ W0 |
| MEM-03 | Agent references past facts via long-term store | integration (mocked store) | `python -m unittest tests.test_memory.LongTermMemoryTests -v` | ❌ W0 |
| MEM-04 | `memory_read`/`memory_write` appear in `intermediate_steps` as Steps | unit | `python -m unittest tests.test_agent.MemoryToolStepTests -v` | ❌ W0 |
| MEM-05 | Session id returned in API response / accessible in UI state | manual (no frontend test framework) | Manual verify | — |
| MEM-06 | Clear memory deletes checkpoint rows AND store rows for the session | integration (mocked DB) | `python -m unittest tests.test_api.ClearMemoryTests -v` | ❌ W0 |
| MEM-07 | Store entries capped at `MAX_MEMORIES_STORED` after writes | unit | `python -m unittest tests.test_memory.MemoryCapTests -v` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_memory.py` — new module: checkpoint restore, long-term recall, memory cap (mocked store + checkpointer)
- [ ] `backend/tests/test_api.py` additions — session_id extraction, clear-memory endpoint (200 + 400 on malformed id), dual-route registration
- [ ] `backend/tests/test_agent.py` additions — `memory_read`/`memory_write` produce Steps in `intermediate_steps`
- [ ] Pool construction (`AsyncConnectionPool` + `prepare_threshold=None`, `supports_pipeline=False`) smoke-tested against real Supabase before Wave 1 memory code lands
- [ ] `SUPABASE_POOLER_URL` / `SUPABASE_DIRECT_URL` valid locally + in Vercel (re-verify after any Supabase resume)

*Existing ~58 tests cover regression; `test_memory.py` is the new Phase 2 scaffolding.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser close + return restores history | MEM-02 / SC1 | Needs real browser session + live Supabase checkpointer | Open app, send a query, close browser, reopen with same persisted session_id → prior messages visible without re-typing |
| Agent references past facts cross-session | MEM-03 / SC2 | Needs two sessions sharing a session_id + live store | Session A: "My name is Paulo and I work at an AI startup." New session, same session_id: "What's my name?" → agent answers "Paulo" |
| `memory_read`/`memory_write` appear as trace Steps | MEM-04 / SC3 | SSE stream rendered in ReasoningPanel | Submit a memory-triggering query; SSE stream contains `action=memory_read`/`memory_write` events visible in the panel |
| Session id visible + copyable in UI | MEM-05 / SC4 | Visual UI element | Inspect UI: session_id shown with copy button; copy → use in `GET /api/trace/...` returns that session's data |
| Clear memory → no recollection next turn | MEM-06 / SC5 | Needs live DB delete + follow-up turn | Click "clear memory"; ask about a previously shared fact → agent has no memory; `SELECT COUNT(*) FROM checkpoints WHERE thread_id=?` = 0 |

### Cross-Session Persistence Round-Trip (SC1 + SC2 + SC5 smoke)

1. Start backend locally with a real `SUPABASE_POOLER_URL`
2. `POST /api/run` with `X-Session-Id: test-session-001`, query = "Remember that my dog is named Rex" → verify a `memory_write` Step appears
3. `POST /api/run` same session_id, query = "What's my dog's name?" → agent answers "Rex" via a `memory_read` Step
4. `DELETE /api/memory/test-session-001`
5. `POST /api/run` same session_id, query = "What's my dog's name?" → agent has no memory of the dog

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (unit suite); round-trip gated by live env
- [ ] `nyquist_compliant: true` set in frontmatter (after task IDs bound)

**Approval:** pending
