# Phase 4: Observability - Research

**Researched:** 2026-07-02
**Domain:** Serverless trace persistence (Supabase/psycopg) + FastAPI read endpoints + React run-history/trace-detail UI
**Confidence:** HIGH (this is almost entirely a codebase-grounded integration phase; the one external unknown — Vercel serverless post-response write semantics — is flagged as an assumption)

## Summary

Phase 4 turns the agent's existing in-memory run traces into durable, reviewable history. The heavy lifting from prior phases is already in place: the `traces` table was created in the Phase 1 migration (`.planning/phases/01-foundation/migration.sql:37-50`), the DB pool is opened in the FastAPI lifespan and threaded into every request (`backend/api.py:117-142`, `464`), and each run already produces a fully-structured trace (`AgentResponse.steps`, `usage`) that is stored in the in-process `RUNS` dict (`backend/api.py:108-110, 231-238`). The work is: (1) write that trace to Supabase without blocking the SSE final event, (2) add read endpoints (`GET /runs` list + a DB-backed `GET /trace/{run_id}`), and (3) build a new run-history + trace-detail UI surface.

Three real gaps must be closed in the plan, not assumed away. **First, per-step `elapsed_ms` is never populated** — `tool_node` builds `Step` dicts with no timing (`backend/agent/graph.py:520-528`); the `elapsed_ms` in the SSE payload is a *cumulative* run-elapsed computed at emit time (`backend/api.py:328`), so a persisted trace would show no per-step duration. OBS-03 requires adding per-step timing in `tool_node`. **Second, fallback events are silently swallowed** — `FreeModelFallback.invoke` collects per-provider exceptions into a local list and only raises if *all* providers fail (`backend/agent/llms.py:46-59`); the `UsageTracker` records only the provider that *succeeded* (`llms.py:421-437`). OBS-04's "Gemini failed → Groq" narrative does not exist anywhere yet and needs minimal instrumentation. **Third, OBS-05 is essentially already done** — `/evals` serves the committed baseline (`backend/api.py:559-570`) and `EvalsSection.tsx` fetches it live on mount and renders it in the About tab (`frontend/src/components/EvalsSection.tsx:38-61`, `PortfolioView.tsx:16`); success criterion 4 is met today. Treat OBS-05 as a verification item, not a build item.

**Primary recommendation:** Persist the trace by `await`-ing a single guarded INSERT *inside the SSE generator, immediately after yielding the final event and before the generator returns* (`backend/api.py:428-439`). This keeps the visible answer non-blocking (already yielded) while keeping the write on the request's own execution path rather than an orphaned `asyncio.create_task`. Keep the in-memory `RUNS` dict as a same-instance fast path. Reuse the `traces` table as-is and store fallback events inside the existing `usage` JSONB to avoid a migration.

## User Constraints

No `CONTEXT.md` exists for this phase (confirmed: `.planning/phases/04-observability/*CONTEXT*` absent). There are no locked user decisions to honor beyond the phase requirements and the project invariants in CLAUDE.md. All decisions below are Claude's discretion, grounded in existing code patterns, and flagged where they need confirmation.

## Project Constraints (from CLAUDE.md)

These are load-bearing invariants the plan must not violate:

- **No OpenAI/Anthropic dependency.** Free-tier providers only (Gemini → Groq → GitHub Models). Do not add a paid trace SaaS. `[CITED: .claude/CLAUDE.md]`
- **Vercel serverless: ephemeral FS, no long-lived processes.** External persistence required; a background write must survive the response returning. `[CITED: .claude/CLAUDE.md]`
- **Secret redaction is global.** `redaction.py` monkey-patches the logging record factory (`configure_secure_logging()` at `backend/api.py:38`). This scrubs *logs*, not DB writes — see Security Domain. `[CITED: CLAUDE.md]`
- **Fire-and-forget must not block the SSE final event.** Explicitly called out. `[CITED: task grounding + README architecture]`
- **Rate limit 10/min per IP** via slowapi (`backend/api.py:114`). Read endpoints for run history interact with this — see Pitfalls. `[CITED: CLAUDE.md]`
- **Every route registered twice** (bare + `/api/` prefix) and needs a `vercel.json` rewrite for the bare path (`vercel.json:32-43`). `[CITED: CLAUDE.md]`
- **`backend/api.py` and `api/index.py` are two entrypoints to the same app.** Vercel deploys from `api/requirements.txt`, not `backend/requirements.txt` (per MEMORY.md `vercel-requirements-drift`) — no new deps here, so not a concern this phase. `[VERIFIED: codebase grep]`
- **`python -m unittest discover -s tests`** is the test runner; no frontend test framework. `[CITED: CLAUDE.md]`

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-01 | Completed runs persisted to Supabase WITHOUT blocking the response (fire-and-forget) | `traces` table exists; recommend await-after-final-yield inside the generator (`api.py:428-439`); keep in-memory `RUNS` as fast path. See Pitfall 1 + Architecture Pattern 1. |
| OBS-02 | UI shows list of recent runs (clickable trace history) | New `GET /runs` (session-scoped via `thread_id`, `ORDER BY created_at DESC LIMIT N`); new React "History" tab; fetch with `X-Session-Id`. `traces_thread_idx` index already exists. |
| OBS-03 | Trace detail view shows each step with `elapsed_ms` | **GAP**: `tool_node` never sets `elapsed_ms` (`graph.py:520-528`). Add `perf_counter` around each tool call. `ReasoningPanel` already renders `step.elapsed_ms` (`ReasoningPanel.tsx:239`). |
| OBS-04 | Each run displays provider used + fallback events | `usage.providers` already lists the winning provider(s). **GAP**: fallback (who *failed*) is swallowed in `FreeModelFallback.invoke` (`llms.py:46-59`). Add a redacted fallback-event collector; store in `usage` JSONB. |
| OBS-05 | Eval results surfaced in UI reflect committed baseline | **DONE**: `/evals` (`api.py:559-570`) + `EvalsSection.tsx` live fetch. Verification only; optionally surface near run history. |
| OBS-06 | Traces local (Supabase) only; no external SaaS; redaction preserved | No langsmith/LANGCHAIN_TRACING in project source (only in `.venv`). Persist to Supabase only. Apply `redact_secrets` to stored error observations defensively. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trace write on run completion | API / Backend (`_stream_agent`, `_run_agent`) | Database (Supabase `traces`) | Only the backend holds the full structured trace + usage; the write must ride the request lifecycle. |
| Per-step timing capture | API / Backend (`tool_node`) | — | Timing is measured where the tool executes; frontend only renders it. |
| Provider/fallback capture | API / Backend (`FreeModelFallback` / `UsageTracker`) | — | Fallback happens below the graph node, inside the provider chain. |
| Run-history list | Database (query) → API (`GET /runs`) | Frontend (render) | Source of truth is Supabase; in-memory `RUNS` is a per-instance cache only. |
| Trace detail render | Frontend (`ReasoningPanel` reuse) | API (`GET /trace/{id}`) | UI already renders Thought/Action/Observe/Final + telemetry; reuse it. |
| Eval panel | Frontend (`EvalsSection`) | API (`GET /evals`) | Already implemented end-to-end. |

## Standard Stack

No new packages. Every capability is served by dependencies already installed and already used by Phases 1–3.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg (async) | 3.x (installed) | Supabase reads/writes via the shared pool | Phase 1/2/3 already use `AsyncConnectionPool` with `prepare_threshold=None` for Supavisor. `[VERIFIED: backend/agent/db.py]` |
| psycopg `Json` adapter | psycopg.types.json | Serialize `steps`/`usage` dicts into JSONB columns | Native psycopg JSONB binding; avoids manual `json.dumps` + cast. `[CITED: psycopg3 docs]` |
| FastAPI | 0.115.4 | New `GET /runs` route, DB-backed `GET /trace/{id}` | Existing framework; double-register + `vercel.json` rewrite pattern. `[VERIFIED: backend/api.py]` |
| React 19 / Vite / TS | installed | New History tab + trace detail | Existing frontend; reuse `ReasoningPanel` timeline. `[VERIFIED: frontend/]` |
| Framer Motion / Radix / lucide-react | installed | Timeline animation, dialogs, icons | Already used by `ReasoningPanel.tsx`. `[VERIFIED: frontend/]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI `BackgroundTasks` | bundled | Post-response write for the *non-streaming* JSON path (`_run_agent`) | Only if you decide not to `await` inline; see Pattern 1 tradeoffs. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| await-inside-generator persist | `asyncio.create_task` fire-and-forget | Rejected: an orphaned task after the response returns can be frozen/killed on serverless (the exact CLAUDE.md constraint). The generator-await keeps the write on the live request path. |
| Store `fallback_events` in `usage` JSONB | `ALTER TABLE traces ADD COLUMN fallback_events JSONB` | JSONB avoids a migration and the schema is already flexible; a dedicated column is cleaner for querying. **Planning decision — see Assumptions Log A3.** |
| Reuse `traces` table as-is | Add a `provider` column | `usage.providers` already carries the winning provider; a separate column duplicates it. Reuse. |

**Installation:** None. `[VERIFIED: no new packages]`

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** All libraries (psycopg, FastAPI, React, Framer Motion, Radix, lucide-react) are already present and vendored from Phases 1–3. No `npm install` / `pip install` step is expected. If the plan introduces a new dependency, run the Package Legitimacy Gate before adding it.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────── WRITE PATH (OBS-01) ───────────────────────────┐
 POST /run (stream) │                                                                            │
      │             │   agent graph (astream)                                                    │
      ▼             │        │  each tool step → Step{thought,action,obs,elapsed_ms*}  (*NEW)     │
 _stream_agent ─────┤        ▼                                                                    │
  (generator)       │   yield thought/action/observation SSE  ── live ──▶ browser ReasoningPanel  │
      │             │        │                                                                    │
      │             │   build_response(...) + _store_response(RUNS)  (in-memory fast path)         │
      │             │        │                                                                    │
      │             │   yield FINAL SSE event  ── answer shown to user (NON-BLOCKING) ──▶ browser  │
      │             │        │                                                                    │
      │             │   await persist_trace(pool, run_id, thread_id, query, steps,                 │
      │             │            final_answer, status, usage+fallback_events, elapsed_ms)          │
      │             │        │  try/except → log+swallow (never surfaces to user)                  │
      │             │        ▼                                                                    │
      │             │   Supabase  traces (INSERT ... ON CONFLICT (run_id) DO NOTHING)              │
      └─────────────┴────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────── READ PATH (OBS-02/03/04) ──────────────────────┐
 GET /runs          │  X-Session-Id header → thread_id                                            │
  (session-scoped)  │  SELECT run_id, query, status, elapsed_ms, usage, created_at                 │
      │             │  FROM traces WHERE thread_id=%s ORDER BY created_at DESC LIMIT N             │
      ▼             │        │                                                                    │
 History tab ◀──────┤        ▼   list items: timestamp · query summary · status · total ms · prov  │
  click run         │  GET /trace/{run_id}  → SELECT ... (DB first, in-memory RUNS fallback)        │
      │             │        ▼   full steps[] with per-step elapsed_ms + fallback_events           │
      ▼             │  reuse ReasoningPanel Timeline for step render                               │
      └─────────────┴────────────────────────────────────────────────────────────────────────────┘

 GET /evals (OBS-05, DONE) → EvalsSection.tsx live fetch → About tab (committed baseline.json)
```

### Recommended Project Structure
```
backend/agent/
├── traces.py           # NEW: persist_trace() + fetch_runs() + fetch_trace() DB helpers
                        #      (mirrors ingest.py / db.py separation of concerns)
backend/api.py          # EDIT: wire persist into _stream_agent + _run_agent; add GET /runs;
                        #       make GET /trace read DB first, RUNS fallback
backend/agent/graph.py  # EDIT: tool_node adds per-step elapsed_ms
backend/agent/llms.py   # EDIT: FreeModelFallback records redacted fallback events into tracker
frontend/src/
├── components/RunHistory.tsx       # NEW: list + detail (reuses ReasoningPanel Timeline)
├── hooks/useRunHistory.ts          # NEW: fetch /runs + /trace with X-Session-Id
├── App.tsx                         # EDIT: add "History" nav item
├── types/index.ts                  # EDIT: RunListItem, TraceDetail, FallbackEvent
vercel.json             # EDIT: add rewrite for bare /runs
.planning/phases/01-foundation/migration.sql  # EDIT only if a migration is chosen for fallback_events
```

### Pattern 1: Non-blocking persist inside the SSE generator (OBS-01)
**What:** After yielding the final SSE event, `await` the DB write inside the same async generator before it returns. The `StreamingResponse` keeps the generator (and thus the function invocation) alive until it is exhausted, so the write runs on the live request path — not an orphaned task.
**When to use:** The streaming path (`_stream_agent`). This is the primary user path (`useAgent.ts:557` always sends `stream: true`).
**Example:**
```python
# backend/api.py _stream_agent, replacing lines 428-439
response = _build_response(run_id, started_at, final_state, tracker.summary())
_store_response(response)                      # in-memory fast path (unchanged)
yield _sse_payload(                            # FINAL event — answer is now visible
    "final", response.result, printed_steps + 1,
    run_id=run_id, started_at=started_at,
    tools_used=response.tools_used, status="success", usage=response.usage,
)
# Persist AFTER the user has their answer, but still on the request's own path.
try:
    if pool is not None:
        await persist_trace(pool, run_id, session_id, query, response)
except Exception:
    logger.exception("trace persist failed for run %s", run_id)   # never surfaces to user
```
**Grounding:** `_stream_agent` already computes `response` and has `pool`, `session_id`, `query`, `run_id` in scope (`backend/api.py:342-439`). `list_documents` shows the `pool is None → degrade` pattern (`api.py:638-640`).

### Pattern 2: Per-step `elapsed_ms` capture (OBS-03)
**What:** Time each tool invocation in `tool_node` and write it into the `Step`.
**Example:**
```python
# backend/agent/graph.py tool_node, around _run_tool (lines 515-528)
import time
step_started = time.perf_counter()
observation = _run_tool(action, action_input)          # (or memory/doc branches)
elapsed_ms = round((time.perf_counter() - step_started) * 1000)
new_steps.append({
    "thought": thought, "action": action, "action_input": action_input,
    "observation": observation,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "elapsed_ms": elapsed_ms,     # NEW — field already declared NotRequired in state.py:15
})
```
**Grounding:** `Step` TypedDict already declares `elapsed_ms: NotRequired[int]` (`state.py:15`); the UI already renders it (`ReasoningPanel.tsx:239`). This closes the loop end-to-end.

### Pattern 3: Fallback-event capture without breaking redaction (OBS-04)
**What:** `FreeModelFallback.invoke` currently discards which providers failed. Pass the `UsageTracker` (or a small collector) into `FreeModelFallback` so that when provider N fails but a later one succeeds, it records a **redacted** event.
**Example:**
```python
# backend/agent/llms.py FreeModelFallback.invoke (lines 46-59)
def invoke(self, messages, tools=None):
    errors = []
    for provider in self.providers:
        try:
            result = provider.call(messages, tools)
            if errors and self._tracker is not None:      # someone failed before this success
                self._tracker.record_fallback(errors)     # errors already redacted below
            return result
        except Exception as exc:
            errors.append({
                "provider": provider.name,
                "error": f"{type(exc).__name__}: {_safe_exception_message(exc)}",  # redacted
            })
    raise RuntimeError("All free model providers failed: " + " | ".join(
        f"{e['provider']}: {e['error']}" for e in errors)) from None
```
Then `UsageTracker.summary()` adds `"fallback_events": self.fallback_events`, which already flows into `response.usage` and into the persisted `usage` JSONB. `_safe_exception_message` already routes through `redact_secrets` (`llms.py:104-105`), preserving OBS-06.
**Wiring note:** `FreeModelFallback` is built in `_create_default_llm` (`graph.py:354-356`) and the tracker is attached one layer up via `UsageTrackingLLM` (`graph.py:548-551`). The fallback happens *inside* `FreeModelFallback`, *below* `UsageTrackingLLM`, so the tracker must be threaded into `FreeModelFallback` directly (constructor arg), not left to the wrapper. **Flag this seam for the planner — it is the trickiest edit.**

### Pattern 4: DB-backed read with in-memory fallback (OBS-02/03)
```python
# backend/api.py get_trace (replacing 573-579)
async def get_trace(run_id: str, request: Request) -> AgentResponse:
    pool = getattr(request.app.state, "pool", None)
    if pool is not None:
        row = await fetch_trace(pool, run_id)      # SELECT ... WHERE run_id=%s
        if row is not None:
            return _response_from_row(row)
    response = RUNS.get(run_id)                     # same-instance fast path
    if response is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return response
```

### Anti-Patterns to Avoid
- **`asyncio.create_task(persist(...))` then return** — the task can be frozen/killed once the response is sent on serverless. This is the specific failure the CLAUDE.md constraint warns about.
- **Awaiting the insert *before* the final SSE yield** — that delays the visible answer by the DB round-trip (~50–150ms). Only acceptable as a fallback if the post-yield await proves unreliable under client-disconnect (see Pitfall 1).
- **Widening the SSE payload schema** — the `StreamEvent` type (`types/index.ts:29-41`) and parser are stable; add run-history fields to new `/runs`/`/trace` response types, not to the stream.
- **Logging raw trace content** — redaction covers logs, but don't add debug logs that dump `steps`/`observation` verbatim.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSONB serialization of `steps`/`usage` | Manual `json.dumps` + `::jsonb` cast string-building | `psycopg.types.json.Json(value)` bound param | Handles escaping/NULL correctly; avoids injection via string concat. |
| Session validation | New regex | `_is_valid_session_id` (`api.py:218-219`) | Already exists and is UUID-strict. |
| Trace step rendering | New timeline component | Reuse `ReasoningPanel` `Timeline`/`TraceStep` (`ReasoningPanel.tsx:152-244`) | Already renders Thought/Action/Observe/Final, `elapsed_ms`, tool, `action_input`, telemetry. |
| Provider/cost display | New usage widget | `TelemetryStrip` (`ReasoningPanel.tsx:262-301`) | Already shows tokens, cost, tools; extend for fallback events. |
| Secret scrubbing | New redactor | `redact_secrets` (`redaction.py`) | Global, tested, monkey-patched at startup. |
| Eval panel | Anything | `EvalsSection.tsx` (already live) | OBS-05 is done. |

**Key insight:** This phase is 80% wiring existing pieces together. The genuinely new code is ~1 DB helper module, ~1 list endpoint, ~3 small edits to graph/llms/api, and ~1 React tab. Resist building a "trace viewer framework."

## Common Pitfalls

### Pitfall 1: Client disconnect cancelling the post-yield write (OBS-01)
**What goes wrong:** `useAgent.ts` calls `await reader.cancel()` immediately after the final event (`useAgent.ts:588-590`). Closing the client connection can prompt Starlette to cancel the server-side streaming task — potentially before the post-yield `await persist_trace(...)` completes.
**Why it happens:** `StreamingResponse` watches for disconnect; a cancelled reader closes the socket.
**How to avoid:** (a) Keep the in-memory `_store_response` *before* the final yield (already true) so a same-instance `GET /trace` still works even if the DB write is cut. (b) Wrap the persist in `try/except` (a `CancelledError` is caught and logged, not fatal). (c) If validation shows writes are being dropped, fall back to awaiting the insert *before* the final yield for correctness over the ~100ms latency cost. **This is the single highest-risk item; the plan must include a test that asserts a row lands in `traces` after a streamed run.**
**Warning signs:** `/runs` list empty after a successful streamed run in production but populated locally.

### Pitfall 2: Rate limit on run-history reads
**What goes wrong:** `GET /runs` + per-run `GET /trace` reads count against the `10/minute` per-IP default limit (`api.py:114`). Opening the History tab and clicking several runs can 429.
**How to avoid:** Consider `@limiter.exempt` on the read endpoints (like `/suggestions` at `api.py:544`), or return the full trace inside the `/runs` list payload so clicking a run needs no second request. **Decorator ordering matters:** `@limiter.exempt` must sit *above* the `@app.get` decorators (outermost) or FastAPI misparses the signature — CLAUDE.md documents this exact footgun.
**Warning signs:** 429s when browsing history.

### Pitfall 3: Supabase paused (free-tier) — graceful degradation
**What goes wrong:** Supabase free tier pauses after ~7 days idle; `pool` is `None` (lifespan except-branch, `api.py:133-137`).
**How to avoid:** Mirror `list_documents`: `pool is None` → `GET /runs` returns `{runs: []}`, persist is skipped, the agent still answers. Never 500 on a missing pool.
**Warning signs:** History tab errors instead of showing an empty state.

### Pitfall 4: Missing `query`/`thread_id` at persist time
**What goes wrong:** `AgentResponse` carries neither the original `query` nor the `session_id`/`thread_id` (`api.py:53-63`), but the `traces` table has both columns.
**How to avoid:** Pass `query` and `session_id` explicitly into `persist_trace` — both are in scope in `_stream_agent`/`_run_agent` (`api.py:344-356`, `458-461`). `thread_id` in the table == `session_id` (they are the same value via `_graph_config`, `api.py:227-228`).

### Pitfall 5: `usage` JSONB shape drift
**What goes wrong:** If `fallback_events` is added inside `usage`, the frontend `Usage` type (`types/index.ts:3-10`) and `_usage_metadata` consumers must tolerate the new key.
**How to avoid:** Make `fallback_events` optional on the TS `Usage` type; default to `[]` server-side so existing consumers are unaffected.

## Code Examples

### Persist helper (new `backend/agent/traces.py`)
```python
# Source: pattern derived from backend/agent/ingest.py + db.py (this repo)
from psycopg.types.json import Json

async def persist_trace(pool, run_id, thread_id, query, response):
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO traces
              (run_id, thread_id, query, steps, final_answer, status, usage, elapsed_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (run_id, thread_id, query, Json(response.steps), response.result,
             response.status, Json(response.usage), response.latency_ms),
        )

async def fetch_runs(pool, thread_id, limit=50):
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT run_id, query, status, elapsed_ms, usage, created_at
            FROM traces WHERE thread_id = %s
            ORDER BY created_at DESC LIMIT %s
            """,
            (thread_id, limit),
        )
        return await cur.fetchall()   # dict_row rows (db.py sets row_factory=dict_row)
```
**Note:** `pool.connection()` yields a `dict_row` connection (`db.py:57`), matching `list_documents`' access-by-key style (`api.py:657-661`).

### Run-history fetch (new `frontend/src/hooks/useRunHistory.ts`)
```ts
// Source: mirrors DocumentPanel/useAgent fetch + X-Session-Id pattern (this repo)
const res = await fetch(`${apiBaseUrl()}/runs`, {
  headers: { Accept: 'application/json', 'X-Session-Id': getOrCreateSessionId() },
})
```
`getOrCreateSessionId()` already exists (`useAgent.ts:25-32`); consider exporting it or duplicating the `react-agent:session-id` localStorage read.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-memory `RUNS` dict per instance | Durable Supabase `traces` | This phase | Traces survive cold starts and are shared across serverless instances. |
| Fire-and-forget via detached task | Await-on-request-path (generator) / Fluid post-response | Vercel Fluid default 2025 | Post-response work is now supported, but the generator-await pattern is more deterministic than relying on Fluid semantics. |
| Silent provider fallback | Recorded, redacted fallback events | This phase | OBS-04 legibility ("Gemini failed → Groq"). |

**Deprecated/outdated:**
- External trace SaaS (LangSmith): present in `.venv` transitively but **not** enabled in project source (no `LANGCHAIN_TRACING_V2`/`LANGSMITH_*` in `backend/*.py`). Do not enable — violates OBS-06 and the free-tier invariant. `[VERIFIED: grep, only .venv hits]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The SSE generator stays alive to complete a post-final-yield `await` on Vercel (Fluid Compute / graceful shutdown), OR the in-memory fast path + try/except covers the gap | Pattern 1, Pitfall 1 | Traces silently dropped in prod; mitigated by validation test + optional await-before-yield fallback. **Highest-risk assumption — validate in prod-like conditions.** |
| A2 | This project runs on Vercel Fluid Compute (now default for new projects) | State of the Art | If on legacy serverless, post-response writes are less reliable → use await-before-yield. Verify in Vercel project settings. |
| A3 | Storing `fallback_events` inside `usage` JSONB (no migration) is acceptable vs. a dedicated column | Standard Stack, Pattern 3 | Low — either works; JSONB is the lower-effort default. Planner should pick explicitly. |
| A4 | `thread_id` (session id) is the correct scoping key for run history, matching memory/RAG session-scoping | Read path, OBS-02 | Low — consistent with Phases 2/3; but note runs made with no/!valid session id get a random UUID (`api.py:222-224`) and won't appear in any session's history. |
| A5 | A recruiter-legible surface is a new "History" nav tab (vs. a panel) | UI | Low — cosmetic; confirm during UI design. |

## Open Questions

1. **Should the `/runs` list embed full step traces, or return summaries + a second fetch per run?**
   - What we know: Embedding avoids a second request and dodges the rate limit (Pitfall 2); summaries keep the list payload small.
   - Recommendation: Return **summaries** in `/runs` (run_id, query, status, elapsed_ms, provider, fallback flag, created_at) and fetch full steps on click via `/trace/{id}`, but `@limiter.exempt` both read endpoints. Balances payload size and rate-limit safety.

2. **Runs without a valid `X-Session-Id` (random UUID) are unreachable in history — is that acceptable?**
   - What we know: `_get_session_id` mints a random UUID when the header is absent/invalid (`api.py:222-224`). The frontend always sends one (`useAgent.ts:555`), so real users are fine; only direct API callers are affected.
   - Recommendation: Accept it; document that history is session-scoped by design.

3. **Retention: cap the `traces` table?**
   - What we know: Free-tier storage is finite; no TTL exists. `RUN_ORDER`/`MAX_STORED_RUNS=100` caps only memory.
   - Recommendation: Out of scope for OBS-01..06, but flag a `LIMIT`-based read + optional periodic prune as a Deferred Idea. `[ASSUMED]`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Supabase Postgres (pooler) | OBS-01/02/03 persist + read | ✓ (used since Phase 1) | Transaction Pooler :6543 | `pool is None` → empty history, skip persist (graceful) |
| `traces` table | OBS-01..04 | ✓ (created in `01-foundation/migration.sql`) | run_id/thread_id/query/steps/final_answer/status/usage/elapsed_ms/created_at | — |
| psycopg async + `Json` | writes/reads | ✓ | 3.x | — |
| No new npm/pip deps | all | ✓ | — | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Supabase pause → degrade to empty history (mirrors `list_documents`).

## Validation Architecture

Nyquist validation is enabled (`config.json workflow.nyquist_validation: true`). Test runner: **Python `unittest`** (`python -m unittest discover -s tests`); no frontend test framework exists (CLAUDE.md). Frontend criteria are validated manually / via QA.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (backend) |
| Config file | none — discovery via `-s tests` |
| Quick run command | `python -m unittest tests.test_traces -v` (new file) |
| Full suite command | `python -m unittest discover -s tests -v` (run from `backend/`) |

### Phase Requirements → Test Map
| Req ID | Behavior (observable signal) | Test Type | Automated Command | File Exists? |
|--------|------------------------------|-----------|-------------------|-------------|
| OBS-01 | After a streamed run, a row with matching `run_id` exists in `traces` AND the final SSE event was emitted before the write | integration (mock/stub pool capturing INSERT) | `python -m unittest tests.test_traces.PersistTests -v` | ❌ Wave 0 |
| OBS-01 | Persist failure (pool raises) does NOT change the streamed answer / does not raise to caller | unit | `python -m unittest tests.test_traces.PersistTests.test_persist_failure_is_swallowed -v` | ❌ Wave 0 |
| OBS-03 | Each persisted `Step` has an integer `elapsed_ms >= 0` | unit (drive `tool_node`) | `python -m unittest tests.test_graph.StepTimingTests -v` | ❌ Wave 0 |
| OBS-04 | When provider 1 raises and provider 2 succeeds, `usage.fallback_events` contains 1 redacted entry naming provider 1; no secret substring present | unit (fake providers) | `python -m unittest tests.test_llms.FallbackEventTests -v` | ❌ Wave 0 |
| OBS-02 | `GET /runs` returns runs for the session ordered `created_at DESC`; empty list when `pool is None` | integration (TestClient) | `python -m unittest tests.test_api.RunsEndpointTests -v` | ❌ Wave 0 (extend `test_api`) |
| OBS-03 | `GET /trace/{id}` returns DB row when present, in-memory fallback otherwise, 404 when neither | integration (TestClient) | `python -m unittest tests.test_api.TraceEndpointTests -v` | ❌ Wave 0 (extend `test_api`) |
| OBS-05 | `/evals` returns committed baseline shape; `status: unavailable` when file missing | integration (already testable) | `python -m unittest tests.test_api -v` | ✅ existing route; add assertion if absent |
| OBS-06 | Persisted `steps`/`final_answer` contain no configured secret value (inject a fake secret into an observation, assert redaction) | unit | `python -m unittest tests.test_traces.RedactionTests -v` | ❌ Wave 0 |

### Success Criteria → Observable Signal
1. **Scrollable list of recent runs** → `GET /runs` returns ≥1 item with `{created_at, query, status, elapsed_ms}`; History tab renders them. Signal: HTTP 200 + non-empty JSON array after a run.
2. **Clicking a run expands step trace with per-step `elapsed_ms`** → `GET /trace/{id}.steps[i].elapsed_ms` is a number; `ReasoningPanel` "elapsed" meta renders. Signal: every step object has `elapsed_ms`.
3. **Provider + fallback events shown** → run/detail payload exposes `usage.providers` (winner) and `usage.fallback_events[]`; forced-fallback test produces a visible "Gemini failed → Groq" entry. Signal: `fallback_events` length matches injected failures.
4. **Eval results match committed baseline without manual refresh** → `EvalsSection` fetch of `/evals` returns `baseline.json` content on mount. Signal: rendered `task_success_rate` == baseline value. **Already passing today.**

### Sampling Rate
- **Per task commit:** `python -m unittest tests.test_traces -v` (or the touched module's test)
- **Per wave merge:** `python -m unittest discover -s tests -v` (from `backend/`)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus a manual prod-like check that a streamed run lands a `traces` row (Pitfall 1 / A1).

### Wave 0 Gaps
- [ ] `backend/tests/test_traces.py` — persist success, swallowed failure, redaction (OBS-01/06)
- [ ] `backend/tests/test_graph.py` StepTimingTests — per-step `elapsed_ms` (OBS-03) *(extend existing file if present)*
- [ ] `backend/tests/test_llms.py` FallbackEventTests — redacted fallback capture (OBS-04)
- [ ] `backend/tests/test_api.py` — extend with `/runs` + DB-backed `/trace` cases (OBS-02/03), using a stub `app.state.pool`
- [ ] Test fixture: an in-memory / stub async pool that records executed SQL + params (no live Supabase in unit tests)

*Note: existing tests set `REACT_AGENT_DISABLE_WEB_SEARCH_GATE=1` — reuse that pattern; keep DB out of unit tests via a stub pool.*

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` (`config.json`). This phase adds a persistence path and two read endpoints — new input/output surfaces.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Portfolio demo; no user auth (existing posture). |
| V3 Session Management | partial | `X-Session-Id` scopes history; validated by `_is_valid_session_id` (UUID-strict). Reuse it — do not trust raw header in a query without validation. |
| V4 Access Control | yes | `/runs` and `/trace/{id}` must scope by `thread_id`. **Risk: `/trace/{id}` currently returns any run by id with no session check.** If run ids are guessable/leakable, one session could read another's trace. Recommend scoping `/trace` by session or accepting the low risk for a demo — **flag for planner.** |
| V5 Input Validation | yes | `run_id` path param and `X-Session-Id` header are user input. Use parameterized psycopg queries (never string-concatenate into SQL). `_is_valid_session_id` for the header. |
| V6 Cryptography | no | No new crypto. |
| V7 Error Handling & Logging | yes | Persist errors are logged via `logger.exception` (already redaction-scrubbed). Do not log raw `steps`. |

### Known Threat Patterns for FastAPI + psycopg + Supabase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via `run_id`/`session_id`/`thread_id` | Tampering | psycopg parameterized queries (`%s` placeholders) — never f-string SQL. Matches existing `list_documents`. |
| Secret leakage into stored trace (`final_answer`, error `observation`) | Information Disclosure | Redaction covers logs only; **apply `redact_secrets` to stored error observations** before INSERT (OBS-06 test). |
| Cross-session trace read via guessable `run_id` | Information Disclosure / Broken Access Control (V4) | Scope `/trace/{id}` by `thread_id`, or explicitly accept for demo. **Planner decision.** |
| Read-endpoint DoS via rate-limit exhaustion | Denial of Service | Keep slowapi limits or `@limiter.exempt` deliberately; embedding trace in `/runs` reduces request count. |
| Storing PII in traces indefinitely | Information Disclosure | Session-scoped + optional retention cap (Open Question 3). |

## Sources

### Primary (HIGH confidence)
- `backend/api.py` — RUNS/RUN_ORDER, `_store_response`, `_stream_agent`, `_run_agent`, `/trace`, `/evals`, lifespan pool wiring, rate limiter, session id handling `[VERIFIED: codebase]`
- `backend/agent/graph.py` — `tool_node` Step construction (no `elapsed_ms`), `FreeModelFallback` wiring `[VERIFIED: codebase]`
- `backend/agent/llms.py` — `FreeModelFallback.invoke` swallowing failures, `UsageTracker`, `redact_secrets` routing `[VERIFIED: codebase]`
- `backend/agent/db.py` — pool/pooler patterns (`prepare_threshold=None`, `dict_row`) `[VERIFIED: codebase]`
- `backend/agent/state.py` — `Step` TypedDict (`elapsed_ms` NotRequired) `[VERIFIED: codebase]`
- `.planning/phases/01-foundation/migration.sql` — `traces` table columns + indexes `[VERIFIED: codebase]`
- `frontend/src/hooks/useAgent.ts`, `App.tsx`, `ChatWorkspace.tsx`, `components/demo/ReasoningPanel.tsx`, `components/EvalsSection.tsx`, `types/index.ts` — UI surfaces, session id, existing eval fetch `[VERIFIED: codebase]`
- `vercel.json`, `.planning/config.json` — rewrites, nyquist/security flags `[VERIFIED: codebase]`

### Secondary (MEDIUM confidence)
- Vercel Fluid Compute docs/changelog — post-response background work, Python runtime support, graceful shutdown `[CITED: vercel.com/docs/fluid-compute, vercel.com/changelog/fluid-compute-is-now-the-default-for-new-projects]`

### Tertiary (LOW confidence)
- Exact reliability of a post-final-yield `await` under client `reader.cancel()` on this project's specific Vercel plan — **must be validated** (Assumption A1/A2).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all patterns exist in-repo.
- Architecture: HIGH — read/write paths grounded in existing routes; one MEDIUM edge (serverless post-response write reliability).
- Pitfalls: HIGH — derived from actual code (rate limiter ordering, pool-None degrade, missing query/thread_id).
- OBS-05: HIGH — verified already implemented end-to-end.

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 (stable; Vercel Fluid behavior is the only fast-moving element)
