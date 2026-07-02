---
phase: 4
slug: observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `04-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (backend); no frontend test framework — frontend criteria validated manually / via QA |
| **Config file** | none — discovery via `-s tests` |
| **Quick run command** | `python -m unittest tests.test_traces -v` (new module) |
| **Full suite command** | `python -m unittest discover -s tests -v` (run from `backend/`) |
| **Estimated runtime** | ~20–40 seconds (current suite ~105 tests) |

*DB stays out of unit tests via a stub async pool that records executed SQL + params. Reuse `REACT_AGENT_DISABLE_WEB_SEARCH_GATE=1` pattern from existing tests.*

---

## Sampling Rate

- **After every task commit:** Run `python -m unittest tests.test_traces -v` (or the touched module's test)
- **After every plan wave:** Run `python -m unittest discover -s tests -v` (from `backend/`)
- **Before `/gsd-verify-work`:** Full suite green **plus** a manual prod-like check that a streamed run lands a `traces` row (Pitfall 1 / Assumption A1)
- **Max feedback latency:** ~40 seconds

---

## Per-Task Verification Map

| Requirement | Wave | Behavior (observable signal) | Test Type | Automated Command | File Exists | Status |
|-------------|------|------------------------------|-----------|-------------------|-------------|--------|
| OBS-01 | 1 | After a streamed run, a `traces` row with matching `run_id` exists AND the final SSE event was emitted before the write | integration (stub pool capturing INSERT) | `python -m unittest tests.test_traces.PersistTests -v` | ❌ W0 | ⬜ pending |
| OBS-01 | 1 | Persist failure (pool raises) does NOT change the streamed answer / does not raise to caller | unit | `python -m unittest tests.test_traces.PersistTests.test_persist_failure_is_swallowed -v` | ❌ W0 | ⬜ pending |
| OBS-03 | 1 | Each persisted `Step` has an integer `elapsed_ms >= 0` | unit (drive `tool_node`) | `python -m unittest tests.test_graph.StepTimingTests -v` | ❌ W0 | ⬜ pending |
| OBS-04 | 1 | When provider 1 raises and provider 2 succeeds, `usage.fallback_events` contains 1 redacted entry naming provider 1; no secret substring present | unit (fake providers) | `python -m unittest tests.test_llms.FallbackEventTests -v` | ❌ W0 | ⬜ pending |
| OBS-02 | 2 | `GET /runs` returns runs for the session ordered `created_at DESC`; empty list when `pool is None` | integration (TestClient) | `python -m unittest tests.test_api.RunsEndpointTests -v` | ❌ W0 (extend `test_api`) | ⬜ pending |
| OBS-03 | 2 | `GET /trace/{id}` returns DB row when present, in-memory fallback otherwise, 404 when neither | integration (TestClient) | `python -m unittest tests.test_api.TraceEndpointTests -v` | ❌ W0 (extend `test_api`) | ⬜ pending |
| OBS-06 | 1 | Persisted `steps`/`final_answer` contain no configured secret value (inject fake secret into an observation, assert redaction) | unit | `python -m unittest tests.test_traces.RedactionTests -v` | ❌ W0 | ⬜ pending |
| OBS-05 | 3 | `/evals` returns committed baseline shape; `status: unavailable` when file missing | integration (already testable) | `python -m unittest tests.test_api -v` | ✅ existing route; add assertion if absent | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_traces.py` — persist success, swallowed failure, redaction (OBS-01/06)
- [ ] `backend/tests/test_graph.py` `StepTimingTests` — per-step `elapsed_ms` (OBS-03) *(extend existing file if present)*
- [ ] `backend/tests/test_llms.py` `FallbackEventTests` — redacted fallback capture (OBS-04)
- [ ] `backend/tests/test_api.py` — extend with `/runs` + DB-backed `/trace` cases (OBS-02/03), using a stub `app.state.pool`
- [ ] Test fixture: an in-memory / stub async pool that records executed SQL + params (no live Supabase in unit tests)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A streamed run actually lands a `traces` row on Vercel | OBS-01 | Serverless post-final-yield `await` reliability under client `reader.cancel()` cannot be reproduced in unit tests (Assumption A1/A2) | Deploy preview, run one query end-to-end, then query Supabase `traces` for the `run_id` and confirm the row exists |
| Run-history list + trace-detail render correctly | OBS-02, OBS-03, OBS-04 | No frontend test framework | QA: submit a run, open History tab, confirm the run appears with timestamp/query/status/elapsed; click it and confirm per-step `elapsed_ms` and provider/fallback display |
| Eval panel matches committed baseline without refresh | OBS-05 | Visual/live-fetch check | Open About tab; confirm rendered `task_success_rate` equals `backend/evals/baseline.json` on mount |

---

## Validation Sign-Off

- [ ] All backend tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter (by planner/checker once mapped)

**Approval:** pending
