---
phase: 02-memory
plan: 01
subsystem: infra
tags: [langgraph, psycopg, postgres, supabase, async, checkpointer, store, fastapi-lifespan]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Supabase project + direct/pooler connection helpers (backend/agent/db.py), keepalive, schema-migration channel decision (5432 for DDL)
provides:
  - Supabase-safe AsyncConnectionPool factory (create_pool) reusing the Phase-1 pooler URL
  - FastAPI lifespan that builds AsyncPostgresSaver (checkpointer) + AsyncPostgresStore on app.state, with graceful degradation when the DB is unreachable
  - build_graph(checkpointer, store) compiling the graph with per-session persistence
  - Async agent invocation path (ainvoke/astream) replacing the sync path
  - X-Session-Id -> validated thread_id config (_get_session_id/_is_valid_session_id/_graph_config)
  - One-time schema-setup script; six LangGraph tables created on the live DB
affects: [02-02, 02-03, 02-04, memory, rag]

# Tech tracking
tech-stack:
  added: [langgraph>=1.2.6, langgraph-checkpoint-postgres>=3.1.0, psycopg-pool>=3.2.0, langchain-core>=1.4.8]
  patterns: [AsyncConnectionPool with prepare_threshold=None/autocommit=True/row_factory=dict_row for Supavisor transaction pooler; supports_pipeline=False on saver+store; lifespan-owned pool on app.state; graceful degradation to None on DB failure; header-derived thread_id validated against canonical UUID]

key-files:
  created:
    - backend/scripts/setup_memory_schema.py
  modified:
    - api/requirements.txt
    - requirements.txt
    - backend/agent/db.py
    - backend/agent/graph.py
    - backend/api.py
    - backend/tests/test_api.py

key-decisions:
  - "Pool via AsyncConnectionPool(prepare_threshold=None, autocommit=True, row_factory=dict_row) — Supavisor transaction pooler (6543) rejects prepared statements; supports_pipeline=False on saver/store for the same reason."
  - "Schema DDL runs ONLY on the direct connection (5432) via a one-time idempotent script — CONCURRENTLY index creation is incompatible with the transaction pooler; lifespan never calls .setup()."
  - "Lifespan wraps pool/checkpointer/store construction in try/except; on any failure app.state.pool/checkpointer/store = None and the agent still answers (graceful degradation)."
  - "Under an active checkpointer, _initial_state seeds ONLY the new HumanMessage (no frontend history) — the operator.add reducer would otherwise duplicate checkpointer-restored messages."
  - "A non-UUID X-Session-Id header is discarded and a fresh uuid4 generated, so no untrusted string reaches the thread_id/namespace (T-02-01)."

patterns-established:
  - "Session persistence: request X-Session-Id -> _get_session_id -> {'configurable': {'thread_id': session_id}} -> graph.ainvoke/astream"
  - "app.state as the single owner of DB-backed resources, created/closed in the FastAPI lifespan"

requirements-completed: [MEM-01, MEM-02]

coverage:
  - id: D1
    description: "api/requirements.txt + root requirements.txt synced to the langgraph 1.x stack (checkpoint-postgres, psycopg-pool) with no OpenAI/Anthropic package; create_pool() factory added to backend/agent/db.py"
    requirement: "MEM-01"
    verification:
      - kind: unit
        ref: "cd backend && .venv/Scripts/python.exe -c \"from agent.db import create_pool\" (exit 0); grep -c langgraph-checkpoint-postgres api/requirements.txt >= 1"
        status: pass
    human_judgment: false
  - id: D2
    description: "FastAPI lifespan builds checkpointer+store on app.state with graceful degradation; build_graph(checkpointer, store); async ainvoke/astream; validated X-Session-Id -> thread_id"
    requirement: "MEM-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_api.py::MemorySessionTests + full suite (65 tests) via .venv/Scripts/python.exe -m unittest discover -s tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "One-time schema-setup script creates the six LangGraph tables on the live Supabase DB (idempotent)"
    requirement: "MEM-02"
    verification:
      - kind: manual_procedural
        ref: "cd backend && .venv/Scripts/python.exe scripts/setup_memory_schema.py -> exit 0 twice (idempotency), non-NULL to_regclass for checkpoints/checkpoint_writes/store"
        status: pass
    human_judgment: false

# Metrics
duration: ~10min
completed: 2026-07-01
status: complete
---

# Phase 2 / Plan 01: Persistence Plumbing Summary

**LangGraph 1.x Postgres checkpointer + store wired through a Supabase-safe async pool and a FastAPI lifespan, with async agent invocation keyed by a validated per-session thread_id — and the six memory tables created on the live DB.**

## Performance

- **Duration:** ~10 min (executor run) + orchestrator-run live DDL
- **Completed:** 2026-07-01
- **Tasks:** 3 (Task 3 completed via orchestrator-run live DDL after the blocking-human gate)
- **Files modified:** 6 modified + 1 created

## Accomplishments
- `create_pool()` — Supabase-safe `AsyncConnectionPool` (prepare_threshold=None, autocommit=True, row_factory=dict_row), reusing the Phase-1 `_pooler_url()`.
- FastAPI `lifespan` builds `AsyncPostgresSaver` + `AsyncPostgresStore` on `app.state` (supports_pipeline=False), degrading to `None` when the DB is unreachable — the agent still answers.
- `build_graph(llm, tracker, checkpointer, store)` compiles the graph with per-session persistence; agent invocation converted to `ainvoke`/`astream`.
- `X-Session-Id` extracted, validated against the canonical UUID pattern, and mapped to `{"configurable": {"thread_id": session_id}}`; malformed/missing headers get a fresh uuid4.
- `_initial_state` no longer re-seeds frontend history when a checkpointer is active (avoids operator.add duplication).
- Live Supabase now has `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`, `store`, `store_migrations` (created idempotently).
- Full backend suite green: **65 tests** (58 prior + 7 new `MemorySessionTests`).

## Task Commits

**No commits were made — per the user's manual-commit workflow, all changes remain uncommitted in the working tree for the user to review and commit.** ([[commit-granularity-large-only]])

- Task 1 — requirements sync + `create_pool` — `api/requirements.txt`, `requirements.txt`, `backend/agent/db.py`
- Task 2 (TDD) — lifespan/async/session_id — `backend/api.py`, `backend/agent/graph.py`, `backend/tests/test_api.py`
- Task 3 — schema-setup script authored + run against live DB — `backend/scripts/setup_memory_schema.py`

## Files Created/Modified
- `backend/scripts/setup_memory_schema.py` (new) — one-time idempotent DDL runner on the direct connection (5432): saver.setup() + store.setup(), verifies via to_regclass, redacted errors, WindowsSelectorEventLoopPolicy.
- `backend/agent/db.py` — added `create_pool()` factory (AsyncConnectionPool, unopened).
- `backend/agent/graph.py` — `build_graph` accepts `checkpointer`/`store` and passes them to `workflow.compile(...)`.
- `backend/api.py` — `lifespan` (pool/checkpointer/store on app.state, graceful degradation); `_get_session_id`/`_is_valid_session_id`/`_graph_config`; `_initial_state(use_checkpointer=...)`; `_run_agent`/`_stream_agent` converted to async ainvoke/astream.
- `backend/tests/test_api.py` — `FakeGraph` gained async `ainvoke`/`astream`; new `MemorySessionTests`.
- `api/requirements.txt`, `requirements.txt` — synced to the langgraph 1.x stack (fixes the Vercel requirements-drift risk, [[vercel-requirements-drift]]).

## Decisions Made
See `key-decisions` frontmatter. Core: pooler-safe pool kwargs; DDL only on the direct connection via the one-time script (never in lifespan); graceful degradation to None; no history re-seed under a checkpointer; UUID-validate the session header.

## Deviations from Plan
None — plan executed as written. Process note: Task 3's live DDL, gated as blocking-human because the executor cannot read `backend/.env`, was run by the orchestrator after the user confirmed (idempotency verified with a second exit-0 run). No commits were created (user's manual-commit workflow).

## Issues Encountered
- Sonnet weekly model limit was hit during checkpoint close-out; the SUMMARY and tracking updates were completed inline by the orchestrator (Opus).

## User Setup Required
None new — reused the Phase-1 `SUPABASE_DIRECT_URL` / `SUPABASE_POOLER_URL` in `backend/.env`. The live schema is now created.

## Next Phase Readiness
- 02-02 (memory_read/memory_write tools) and 02-03 (frontend session-id) are unblocked: the store is on `app.state.store`, the graph compiles with it, and the session thread_id flows from the header.
- Open: `backend/requirements.txt` remains the UTF-16 source of truth; `api/requirements.txt`/`requirements.txt` are UTF-8 and now in sync — keep them in sync in later plans.

---
*Phase: 02-memory*
*Completed: 2026-07-01*
