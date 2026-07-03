---
phase: 04-observability
plan: 02
subsystem: trace-persistence
tags: [supabase, psycopg, jsonb, redaction, fastapi, limiter-exempt, vercel-rewrite, tdd]

# Dependency graph
requires:
  - phase: 04-observability
    plan: 01
    provides: "tool_node Step['elapsed_ms'], usage.fallback_events (UsageTracker.summary)"
  - phase: 01-foundation
    provides: "traces table (run_id, thread_id, query, steps, final_answer, status, usage, elapsed_ms) from migration.sql; shared dict_row/autocommit psycopg pool (agent.db)"
  - phase: 02-memory
    provides: "_get_session_id / X-Session-Id session scoping; RUNS in-memory trace store; redaction.redact_secrets"
provides:
  - "backend/agent/traces.py — persist_trace / fetch_runs / fetch_trace / _response_from_row"
  - "persist_trace wired into _stream_agent (after final SSE yield) and _run_agent (after _store_response), both guarded by try/except (never blocks or breaks the answer)"
  - "GET /runs (+ /api/runs) — session-scoped, newest-first run summaries; empty when pool is None"
  - "GET /trace/{run_id} (+ /api/trace) — DB-first via fetch_trace, in-memory RUNS fallback, 404 when neither"
  - "vercel.json /runs -> /api/index.py rewrite"
affects: [04-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-blocking persistence: the INSERT is awaited on the request's own path AFTER the final SSE yield (streaming) / after _store_response (non-streaming) — never asyncio.create_task (orphaned tasks die on serverless), never before the visible answer"
    - "Redaction-before-store: steps (thought/observation/action_input) and final_answer scrubbed via redact_secrets into a shallow-copied list; the live response is never mutated"
    - "Parameterized SQL only: psycopg %s params for run_id/thread_id/query; ON CONFLICT (run_id) DO NOTHING for idempotent re-persist; steps + usage wrapped in psycopg.types.json.Json"
    - "Graceful degradation: pool is None -> persist no-ops, fetch_runs -> [], /runs -> {runs: []}, /trace -> in-memory fallback (mirrors list_documents)"
    - "@limiter.exempt placed OUTERMOST (above both @app.get decorators) to avoid the FastAPI 422 signature footgun documented in CLAUDE.md"

key-files:
  created:
    - backend/agent/traces.py
    - backend/tests/test_traces.py
  modified:
    - backend/api.py
    - vercel.json
    - backend/tests/test_api.py

key-decisions:
  - "INSERT column/param order fixed as (run_id, thread_id, query, steps, final_answer, status, usage, elapsed_ms); tests pin params[4] == redacted final_answer and exactly 2 Json-wrapped params (steps + usage)"
  - "GET /trace is DB-first then RUNS fallback so freshly-completed in-memory runs remain retrievable even before/without a DB; 404 only when both miss"
  - "T-4-05 IDOR MITIGATED (was accepted in plan): fetch_trace(pool, run_id, thread_id) filters WHERE run_id = %s AND thread_id = %s, and get_trace passes _get_session_id(request), so a run is only readable by its owning session. /runs is likewise strictly thread_id-scoped. Residual: the ephemeral in-memory RUNS fallback is not yet ownership-checked (single-process, short-lived on serverless) — noted for a follow-up."

requirements-completed: [OBS-01, OBS-02, OBS-03, OBS-06]

coverage:
  - id: T1
    description: "persist_trace inserts a parameterized, JSONB-wrapped, redaction-scrubbed row; no-op when pool is None; does not mutate the live response"
    requirement: OBS-01
    verification:
      - kind: unit
        ref: "tests/test_traces.py::PersistTests, ::RedactionTests"
        status: pass
  - id: T2
    description: "GET /runs returns session-scoped (WHERE thread_id = %s) rows and an empty list when pool is None"
    requirement: OBS-02
    verification:
      - kind: unit
        ref: "tests/test_api.py::RunsEndpointTests::test_runs_empty_when_no_pool, ::test_runs_scoped_by_session; tests/test_traces.py::FetchTests"
        status: pass
  - id: T3
    description: "GET /trace/{id} is DB-first with in-memory fallback and 404 when neither; persisted steps preserve per-step elapsed_ms"
    requirement: OBS-03
    verification:
      - kind: unit
        ref: "tests/test_api.py::TraceEndpointTests::test_trace_db_first, ::test_trace_memory_fallback, ::test_trace_404; tests/test_traces.py::FetchTests::test_response_from_row"
        status: pass
  - id: T4
    description: "Persisted steps + final_answer are redaction-scrubbed; no configured secret value is stored"
    requirement: OBS-06
    verification:
      - kind: unit
        ref: "tests/test_traces.py::RedactionTests::test_secret_not_stored, ::test_persist_does_not_mutate_live_response"
        status: pass
  - id: T5
    description: "GET /trace is session-scoped (T-4-05 IDOR mitigation): a persisted trace is only readable by its owning thread_id"
    requirement: OBS-06
    verification:
      - kind: unit
        ref: "tests/test_traces.py::FetchTests::test_fetch_trace_scoped_by_thread; tests/test_api.py::TraceEndpointTests::test_trace_db_first (asserts DB queried with (run_id, session_id))"
        status: pass

# Metrics
duration: split (2 stalled background agents + inline completion)
completed: 2026-07-02
status: complete
---

# Phase 4 Plan 02: Trace Persistence + Read Endpoints Summary

**Completed runs are now durably persisted to Supabase without blocking the answer, and a session's history plus any run's full trace are served over HTTP — rate-limit-safe, redaction-safe, and Vercel-routable. Reuses the existing `traces` table (no migration) and the shared psycopg pool. Consumes 04-01's per-step `elapsed_ms` and `usage.fallback_events`.**

## Accomplishments
- `backend/agent/traces.py` (new): `persist_trace` (guarded pool-None no-op; parameterized `INSERT ... ON CONFLICT (run_id) DO NOTHING`; `steps`/`usage` JSONB-wrapped; `redact_secrets` applied to `final_answer` and step string fields via a shallow copy, leaving the live response untouched), `fetch_runs` (session-scoped, `ORDER BY created_at DESC LIMIT`), `fetch_trace` (single row), `_response_from_row` (rebuilds `AgentResponse`, deriving `tools_used` from step actions).
- `backend/api.py`: imports the traces helpers; `persist_trace` awaited in `_stream_agent` AFTER the final SSE `yield` and in `_run_agent` after `_store_response`, each in `try/except` (persist failure is logged and swallowed). New `RunListItem`/`RunListResponse` models. `GET /runs` (+ `/api/runs`) and DB-first `GET /trace/{run_id}` (+ `/api/trace`), both double-registered with `@limiter.exempt` outermost.
- `vercel.json`: added the `{"source": "/runs", "destination": "/api/index.py"}` rewrite.
- Tests: `backend/tests/test_traces.py` (PersistTests, RedactionTests, FetchTests — parameterized/scoped SQL, redaction-without-mutation, `_response_from_row`) and `backend/tests/test_api.py::RunsEndpointTests`/`::TraceEndpointTests` (pool-None empty list, session scoping, DB-first, in-memory fallback, 404).

## Verification
- `python -m unittest tests.test_traces tests.test_api -v` → **OK**.
- New endpoint tests `RunsEndpointTests` + `TraceEndpointTests` → **Ran 5 tests, OK**.
- `python -m unittest discover -s tests` → **Ran 123 tests, FAILED (failures=1)** — the single failure is the pre-existing, unrelated `test_agent.GraphTests.test_web_search_gate_ignores_year_numbers_in_math` (known baseline). No new failures.
- **Manual (deferred to user):** prod-like check — deploy a preview, run one streamed query, `SELECT * FROM traces WHERE run_id = '<id>'` to confirm the row lands; if rows drop under client disconnect, fall back to awaiting the INSERT before the final yield (tradeoff documented in 04-RESEARCH §Pitfall 1). Not runnable offline.

## Task Commits
Per project git policy the USER commits manually — this run made ZERO commits and staged nothing. All changes are uncommitted working-tree edits.

## Execution Note (non-code)
This plan was executed across two background subagents that both hit infrastructure stream-stalls (not code hangs — the RED tests fail fast on `ModuleNotFoundError`). The first stalled after writing `test_traces.py`; the second completed `traces.py`, the api.py wiring, both endpoints, and the `vercel.json` rewrite before stalling while adding the endpoint tests. The orchestrator verified the landed work green, then completed the missing `RunsEndpointTests`/`TraceEndpointTests` inline and wrote this summary. No deviation from the plan's design.

## User Setup Required
None to run/test. For production persistence, the Supabase `traces` table (already created in 01-foundation `migration.sql`) and a live pool are required; without a pool the endpoints degrade gracefully.

---
*Phase: 04-observability* · *Completed: 2026-07-02*
