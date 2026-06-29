---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [langgraph, langchain, psycopg, postgres, dependencies, requirements]

# Dependency graph
requires: []
provides:
  - Upgraded LangChain/LangGraph ecosystem (langgraph 1.2.6, langchain-core 1.4.8) compatible with the Postgres checkpoint stack
  - New Phase 1 DB packages installed (langgraph-checkpoint-postgres 3.1.0, psycopg 3.3.4, psycopg-pool 3.3.1)
  - Verified AsyncPostgresSaver import path (langgraph.checkpoint.postgres.aio) for Phase 2 memory
  - Confirmed resolved version set for downstream plans to pin against
affects: [01-02, 01-03, 01-04, phase-02-memory, phase-03-rag, phase-04-observability, phase-05-mcp]

# Tech tracking
tech-stack:
  added:
    - langgraph-checkpoint-postgres==3.1.0
    - psycopg[binary]==3.3.4
    - psycopg-pool==3.3.1
  patterns:
    - ">= minimum version constraints for the langchain ecosystem (let pip resolve the compatible set) instead of == exact pins"

key-files:
  created: []
  modified:
    - backend/requirements.txt

key-decisions:
  - "Replace == exact pins with >= minimums across the full langchain ecosystem so pip resolves a conflict-free 1.x set"
  - "Remove explicit langgraph-checkpoint and langgraph-sdk pins — they resolve transitively (checkpoint 4.1.1, sdk 0.4.2) and explicit pins cause conflicts"
  - "Preserve UTF-16 LE BOM + CRLF encoding of requirements.txt to avoid pip parse breakage"

patterns-established:
  - "LangChain ecosystem version policy: >= minimums, not == pins, to allow transitive resolution"

requirements-completed: [FOUND-05]

coverage:
  - id: D1
    description: "Full backend unit suite (5 modules) passes on the upgraded langgraph 1.2.6 ecosystem with zero regressions"
    requirement: "FOUND-05"
    verification:
      - kind: unit
        ref: "cd backend && python -m unittest discover -s tests -v (54 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "AsyncPostgresSaver imports cleanly from langgraph.checkpoint.postgres.aio"
    requirement: "FOUND-05"
    verification:
      - kind: integration
        ref: "python -c \"from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver\""
        status: pass
    human_judgment: false
  - id: D3
    description: "pip resolves the upgraded langchain ecosystem + new DB packages with no dependency conflict"
    requirement: "FOUND-05"
    verification:
      - kind: integration
        ref: "pip install -r requirements.txt && pip check (No broken requirements found)"
        status: pass
    human_judgment: false

# Metrics
duration: ~20min
completed: 2026-06-29
status: complete
---

# Phase 1 Plan 01: LangGraph Ecosystem Upgrade Summary

**Upgraded the LangChain/LangGraph ecosystem from 0.2.45 to langgraph 1.2.6 / langchain-core 1.4.8 and installed the Postgres checkpoint stack (langgraph-checkpoint-postgres 3.1.0, psycopg 3.3.4) with the full 54-test backend suite green and zero source changes.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-06-29T18:35:35Z
- **Tasks:** 2 (plus 1 blocking-human checkpoint)
- **Files modified:** 1

## Accomplishments
- Replaced every `==` exact pin in the langchain ecosystem with `>=` minimums and added three net-new Phase 1 DB packages, letting pip resolve a single conflict-free set.
- `pip install -r requirements.txt` resolved cleanly; `pip check` reports "No broken requirements found" — Open Question 2 (langchain-classic conflict) did not materialize; `langchain-classic 1.0.8` installed transitively without issue.
- Full backend unit suite (54 tests across test_agent, test_api, test_llms, test_redaction, test_suggestions) passes on the new runtime with no source modifications and no weakened assertions.
- `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver` resolves — the Phase 2 memory import path is now available.

## Resolved Version Set (pip freeze)

Downstream plans should pin against this confirmed set:

```
langchain==1.3.11
langchain-classic==1.0.8        # transitive (langchain-community 0.4.2)
langchain-community==0.4.2
langchain-core==1.4.8
langchain-protocol==0.0.18      # transitive
langchain-text-splitters==1.1.2
langgraph==1.2.6
langgraph-checkpoint==4.1.1     # transitive (langgraph-checkpoint-postgres)
langgraph-checkpoint-postgres==3.1.0
langgraph-prebuilt==1.1.0       # transitive (langgraph 1.2.6)
langgraph-sdk==0.4.2            # transitive (langgraph 1.2.6)
langsmith==0.9.3
psycopg==3.3.4
psycopg-binary==3.3.4
psycopg-pool==3.3.1
```

New transitive packages pulled in by the upgrade: `langchain-classic`, `langchain-protocol`, `langgraph-prebuilt`, `uuid-utils`, `websockets`, `xxhash`, `zstandard`, `tzdata`.

## Task Commits

1. **Task 1: Rewrite the langchain-ecosystem pins in requirements.txt** - `7cfea3e` (chore)

**Plan metadata:** single docs commit (SUMMARY.md + STATE.md + ROADMAP.md) — see final commit.

_Task 2 (install + test run) produced no source changes — it is a verification gate, not a code-producing task, so it has no separate commit._

## Files Created/Modified
- `backend/requirements.txt` - LangChain ecosystem pins changed from `==` to `>=`; `langgraph-checkpoint==2.1.2` and `langgraph-sdk==0.1.74` lines removed; added `langgraph-checkpoint-postgres>=3.1.0`, `psycopg[binary]>=3.2.0`, `psycopg-pool>=3.2.0`; `numpy==1.26.4` and all non-langchain pins untouched; UTF-16 LE BOM + CRLF preserved.

## Decisions Made
- **`>=` minimums over `==` pins for the langchain ecosystem:** exact pins create irresolvable conflicts on upgrade (RESEARCH Pitfall 4). Minimums let pip resolve the compatible 1.x set.
- **Removed explicit `langgraph-checkpoint` / `langgraph-sdk` pins:** they resolve transitively (4.1.1 / 0.4.2 respectively); explicit pins would fight the resolver.
- **Preserved the file's UTF-16 LE BOM + CRLF encoding** by rewriting via a Python script rather than the Edit tool, which would have corrupted the encoding.

## Deviations from Plan

None - plan executed exactly as written. No transitive pin needed relaxing (the RESEARCH-flagged `langchain-community` → `langchain-classic` risk did not produce a conflict).

## Issues Encountered
- The existing `backend/.venv` had no `pip` module (`No module named pip`). Resolved by bootstrapping with `python -m ensurepip --upgrade` (pip 25.0.1) before installing — no impact on the dependency set. This is a venv-state issue, not a plan deviation.
- Several test cases (e.g. `test_no_configured_provider_falls_back`, `test_stream_run_reports_graph_startup_errors_as_final_event`) print tracebacks by design — they assert error-handling/fallback paths. Final result was `OK` with 0 failures / 0 errors across all 54 tests.

## User Setup Required
None - no external service configuration required for this plan. (Supabase/Vercel env wiring belongs to later Phase 1 plans.)

## Next Phase Readiness
- FOUND-05 satisfied: LangGraph upgraded to a version compatible with `langgraph-checkpoint-postgres` (and forward-compatible with `langchain-mcp-adapters` per RESEARCH), existing tests green.
- Downstream persistence plans (01-02 db connection layer, 01-03 migration, 01-04 keep-alive) are unblocked.
- The `AsyncPostgresSaver` import path is confirmed available for Phase 2 memory work.

## Self-Check: PASSED

- `backend/requirements.txt` exists and contains the upgraded pins (verified).
- Commit `7cfea3e` exists in git history (verified).

---
*Phase: 01-foundation*
*Completed: 2026-06-29*
