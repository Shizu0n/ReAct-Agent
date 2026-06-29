# Phase 1: Foundation — Research

**Researched:** 2026-06-29
**Domain:** Supabase/pgvector persistence backbone, psycopg3 connection layer, Vercel cron keep-alive, LangGraph ecosystem upgrade
**Confidence:** MEDIUM-HIGH on connection and cron patterns (confirmed via official docs); MEDIUM on LangGraph upgrade (confirmed no API breakage, actual test-suite run still needed as the final gate)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Supabase project provisioned with pgvector enabled and required env vars wired in Vercel and `.env.example` | Supabase free tier confirmed: 500 MB, pgvector included, 60 direct / 200 pooler connections. Two env vars needed: `SUPABASE_POOLER_URL` (port 6543) and `SUPABASE_DIRECT_URL` (port 5432). |
| FOUND-02 | Shared DB connection layer using Transaction Pooler (port 6543, prepared statements disabled) for queries and direct (5432) for migrations | psycopg 3.3.4 confirmed on PyPI. `prepare_threshold=None` + `autocommit=True` is the correct pattern for Supabase Supavisor transaction mode. |
| FOUND-03 | Schema migration creates `documents`, `document_chunks`, `traces`, `keepalive` tables plus HNSW vector index | Exact SQL provided in Code Examples. pgvector HNSW syntax confirmed via official pgvector README: `vector_cosine_ops`, m=16, ef_construction=64 defaults. |
| FOUND-04 | Scheduled keep-alive writes to DB at least every 5 days to prevent 7-day inactivity pause | Vercel Hobby: 100 cron jobs allowed, once-per-day minimum interval. Daily cron (`0 0 * * *`) is the correct schedule. Supabase confirmed pauses at 7 days; a DB write counts as activity. |
| FOUND-05 | LangGraph upgraded to version compatible with `langgraph-checkpoint-postgres` and `langchain-mcp-adapters`, existing unit tests still pass | Full dependency chain verified via PyPI wheel inspection. Target: `langgraph==1.2.6` + `langchain==1.3.11` + `langchain-core>=1.4.8`. No breaking changes in the APIs used by this codebase (message types, StateGraph, add_conditional_edges). Must run `python -m unittest discover -s tests -v` post-upgrade as final gate. |
</phase_requirements>

---

## Summary

Phase 1 builds the persistence backbone that every subsequent phase imports. All five requirements are infrastructure — no user-facing UI changes, no new agent behavior. They gate every other phase.

**The most important finding:** The project research said "langgraph >=0.3 is required." The reality is far larger: the full dependency chain from `langgraph-checkpoint-postgres==3.1.0` through `langgraph-checkpoint>=4.1.0` leads to `langgraph>=1.2.0` and `langchain-core>=1.4.7`. The gap is 0.2.45 → 1.2.6 — virtually the entire LangChain ecosystem upgrades in a single step. The good news: LangGraph 1.0 was released explicitly as "no breaking changes," and the project's source code only uses stable imports (`langchain_core.messages.*`, `langgraph.graph.*`) that survived the transition intact. A unit-test run post-upgrade is the final confirmation gate.

**The second most important finding:** Old research documented "1 cron job per project on Hobby." This is wrong as of 2026. Vercel Hobby allows **100 cron jobs** with a **once-per-day minimum interval**. The keep-alive design is therefore: daily cron (`0 0 * * *`) to a FastAPI endpoint that does a single `UPDATE keepalive SET pinged_at = NOW()`, authenticated by checking the `Authorization: Bearer $CRON_SECRET` header that Vercel sends automatically.

**Primary recommendation:** Execute the LangGraph upgrade as an isolated spike first (new venv, pip install, run tests), then build FOUND-01 through FOUND-04 on the confirmed package set. Do not write persistence code before the upgrade is verified.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Supabase connection factory | API / Backend (`backend/agent/db.py`) | — | Serverless: open and close per request; no module singleton |
| Schema migration | Database / Storage (raw SQL via Supabase CLI or MCP) | — | DDL runs once, outside the app; use direct connection (5432) |
| Keep-alive ping | API / Backend (FastAPI route `GET /api/keepalive`) | CDN / Vercel Cron | Vercel cron invokes a GET; FastAPI writes to DB |
| Package version management | API / Backend (`backend/requirements.txt`) | — | Pip install on deploy; no runtime resolution |
| pgvector HNSW index | Database / Storage | — | Created as DDL; no application-layer involvement |

---

## Standard Stack

### Core — Phase 1 New Packages

| Library | Verified Version | Purpose | Why This One |
|---------|-----------------|---------|--------------|
| `psycopg[binary]` | 3.3.4 [VERIFIED: pypi registry] | Async Postgres driver | Only driver that disables prepared statements cleanly for Supavisor transaction mode (`prepare_threshold=None`) |
| `psycopg-pool` | 3.2.x [VERIFIED: pypi registry] | Connection pooling | Required by `langgraph-checkpoint-postgres`; avoids per-request cold connection |
| `langgraph-checkpoint-postgres` | 3.1.0 [VERIFIED: pypi registry] | LangGraph Postgres saver | Provides `AsyncPostgresSaver` (short-term memory, Phase 2) and `PostgresStore` (long-term, Phase 2); must install now to set up tables |
| `orjson` | 3.11.8 (already pinned) | Fast JSON serialization | Transitive requirement of `langgraph-checkpoint-postgres>=3.1.0` |

### Upgraded LangChain Ecosystem (FOUND-05)

| Library | Current Pin | Target | Notes |
|---------|------------|--------|-------|
| `langgraph` | 0.2.45 | >=1.2.6 | Pulled transitively by `langchain==1.3.11` |
| `langgraph-checkpoint` | 2.1.2 | >=4.1.1 | Pulled by checkpoint-postgres 3.1.0 |
| `langgraph-sdk` | 0.1.74 | >=0.4.2 | Pulled by langgraph 1.2.6 |
| `langchain` | 0.3.7 | >=1.3.11 | Drives the whole ecosystem; 1.3.11 requires langgraph >=1.2.5 |
| `langchain-core` | 0.3.63 | >=1.4.8 | Required by langgraph 1.2.6 and langchain 1.3.11 |
| `langchain-community` | 0.3.7 | >=0.4.2 | Latest compatible with langchain-core 1.x; adds `langchain-classic` transitive dep |
| `langchain-text-splitters` | 0.3.8 | >=1.1.2 | Requires langchain-core >=1.2.31 |
| `langsmith` | 0.1.147 | >=0.9.3 | Required by langchain-community 0.4.2 (>=0.1.125) |

**New transitive packages (pip handles automatically):**
- `langgraph-prebuilt>=1.1.0` (pulled by langgraph 1.2.6)
- `langchain-classic>=1.0.7` (pulled by langchain-community 0.4.2)
- `xxhash>=3.5.0` (pulled by langgraph 1.2.6)
- `ormsgpack>=1.12.0` (pulled by langgraph-checkpoint 4.x)
- `pydantic>=2.7.4` (current: 2.13.3, already satisfied)

**Minimum version set for MCP compatibility (Phase 5 future-proofing):**
- `langchain-mcp-adapters>=0.1.14` requires `langchain-core>=0.3.36,<2.0.0` AND `mcp>=1.9.2`
- `langchain-mcp-adapters==0.3.0` requires `langchain-core>=1.0.0,<2.0.0` (also satisfied by the target set)
- Either version works with the target langchain-core; 0.1.14 is more conservative; 0.3.0 is current

**Installation (requirements.txt changes):**
```
# UPGRADE: Remove exact pins for these, replace with minimums
langgraph>=1.2.6
langchain>=1.3.11
langchain-core>=1.4.8
langchain-community>=0.4.2
langchain-text-splitters>=1.1.2
langsmith>=0.9.3

# NEW packages for Phase 1
langgraph-checkpoint-postgres>=3.1.0
psycopg[binary]>=3.2.0
psycopg-pool>=3.2.0
```

Note: `langgraph-checkpoint` and `langgraph-sdk` do NOT need explicit pins — pip resolves them as transitive requirements. Adding explicit pins can cause version conflicts.

### Alternatives Rejected

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg[binary] | asyncpg | asyncpg prepared statements break with Supabase Supavisor transaction mode; psycopg3 has `prepare_threshold=None` |
| psycopg[binary] | psycopg2 | psycopg2 is sync-only; async required for FastAPI |
| langgraph 1.2.6 | langgraph 1.1.x | 1.1.x allows checkpoint 4.x but has more lax langchain-core constraint (>=0.1); going to 1.2.6 locks in langchain-core 1.4.x now rather than getting surprised later |

---

## Package Legitimacy Audit

All packages discovered via official PyPI registry and official GitHub repos. Legitimacy tool flags them all as SUS due to `unknown-downloads` (PyPI weekly downloads not queryable by the tool), but each is from a known, maintained organization.

| Package | Registry | Repo | Verdict | Disposition |
|---------|----------|------|---------|-------------|
| `langgraph` | PyPI | github.com/langchain-ai/langgraph | SUS (unknown downloads) | Approved — official LangChain AI project |
| `langgraph-checkpoint-postgres` | PyPI | github.com/langchain-ai/langgraph | SUS (unknown downloads) | Approved — sub-library of official LangGraph repo |
| `psycopg` | PyPI | psycopg.org | SUS (unknown downloads) | Approved — PostgreSQL official Python adapter |
| `psycopg-pool` | PyPI | psycopg.org | SUS (unknown downloads) | Approved — companion package from same org |

**Packages removed due to SLOP verdict:** none
**Packages flagged SUS (requires user action):** none — all SUS verdicts are false positives due to tool's inability to query PyPI download counts. Packages are from authoritative organizations with documented source repos.

*Note: All packages were verified on the correct ecosystem (PyPI, not npm) and have official repository links matching the publishing organization.*

---

## Architecture Patterns

### System Architecture Diagram

```
[Vercel Cron (daily 00:00 UTC)]
         |
         | GET /api/keepalive
         | Authorization: Bearer $CRON_SECRET
         v
[FastAPI api.py]
    /api/keepalive  ──► [db.py: pooler_connection()] ──► [Supabase port 6543 (Supavisor)]
    /keepalive                                                        |
                                                              UPDATE keepalive
                                                              SET pinged_at=NOW()
                                                              WHERE id=1

[FastAPI api.py: startup lifespan]
         |
         ├──► [db.py: direct_connection()] ──► [Supabase port 5432 (direct)]
         |         CREATE EXTENSION IF NOT EXISTS vector;
         |         (migration — one-time setup)
         |
         └──► (Phase 2: AsyncPostgresSaver.setup() via pooler)

[Agent requests (existing flow, unchanged)]
[build_graph()] ──► [StateGraph] ──► [agent_node] ──► [tool_node]
                                         (no DB in Phase 1)
```

Data flow for keep-alive: Vercel Cron → HTTP GET with Bearer token → FastAPI route validates token → psycopg3 AsyncConnection to pooler (port 6543, prepare_threshold=None) → single UPDATE → 200 OK.

### Recommended Project Structure (new files only)

```
backend/
├── agent/
│   └── db.py          (NEW) — connection factory for pooler + direct
├── api.py             (EDIT) — add /api/keepalive + /keepalive routes
├── requirements.txt   (EDIT) — package upgrades + new deps
.env.example           (EDIT) — add SUPABASE_POOLER_URL, SUPABASE_DIRECT_URL, CRON_SECRET
vercel.json            (EDIT) — add cron job
.planning/phases/01-foundation/migration.sql  (NEW) — schema migration SQL (run manually)
```

### Pattern 1: psycopg3 Pooler Connection Factory

**What:** A context-manager-based connection factory in `backend/agent/db.py` that returns a pooler connection (for all application queries) or a direct connection (migrations only).

**When to use:** Every database write/read in the application (Phase 1: keepalive; Phase 2: checkpointer; Phase 3: document chunks; Phase 4: traces).

```python
# backend/agent/db.py
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg.rows import dict_row


def _pooler_url() -> str:
    url = os.environ.get("SUPABASE_POOLER_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_POOLER_URL is not set")
    return url


def _direct_url() -> str:
    url = os.environ.get("SUPABASE_DIRECT_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_DIRECT_URL is not set")
    return url


@asynccontextmanager
async def pooler_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Async connection to Supabase Transaction Pooler (port 6543).
    Use for all application queries. prepare_threshold=None disables
    prepared statements, which are incompatible with PgBouncer transaction mode.
    """
    async with await psycopg.AsyncConnection.connect(
        _pooler_url(),
        prepare_threshold=None,   # required: Supavisor transaction mode
        autocommit=True,          # required: AsyncPostgresSaver (Phase 2)
        row_factory=dict_row,     # required: AsyncPostgresSaver (Phase 2)
    ) as conn:
        yield conn


@asynccontextmanager
async def direct_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Async connection to Supabase direct (port 5432).
    Use ONLY for schema migrations. Not safe under serverless concurrent load.
    """
    async with await psycopg.AsyncConnection.connect(
        _direct_url(),
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        yield conn
```

### Pattern 2: Keep-Alive Endpoint

**What:** A FastAPI route called by Vercel Cron daily that writes a timestamp to `keepalive`. Authenticated via `CRON_SECRET` Bearer token.

```python
# Addition to backend/api.py — register BOTH bare and /api/ prefixed per CLAUDE.md convention
from fastapi import Request, Response
from datetime import datetime, timezone

@app.get("/keepalive")
@app.get("/api/keepalive")
async def keepalive_handler(request: Request) -> dict:
    cron_secret = os.getenv("CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    if cron_secret and auth != f"Bearer {cron_secret}":
        return Response(status_code=401)

    from agent.db import pooler_connection
    async with pooler_connection() as conn:
        await conn.execute(
            "UPDATE keepalive SET pinged_at = %s WHERE id = 1",
            (datetime.now(timezone.utc),),
        )
    return {"status": "ok", "pinged_at": datetime.now(timezone.utc).isoformat()}
```

### Pattern 3: Vercel Cron Configuration

```json
// vercel.json — add inside the existing JSON object
{
  "crons": [
    {
      "path": "/api/keepalive",
      "schedule": "0 0 * * *"
    }
  ]
}
```

**Cron expression analysis:** `0 0 * * *` = "at 00:00 UTC every day." This runs once per day (Hobby plan maximum frequency) and fires 7x within the 7-day pause window. Vercel Hobby precision is ±59 minutes, so actual execution is 00:00–00:59 UTC. Safe margin before 7-day pause: 6 days minimum.

**Also add** `CRON_SECRET` as an environment variable in Vercel dashboard. Vercel will automatically send `Authorization: Bearer <CRON_SECRET>` with every cron invocation.

### Anti-Patterns to Avoid

- **Using port 5432 for application queries:** Connection exhaustion. Supabase free tier has 60 direct connections. Vercel cold starts multiply this fast. Port 5432 is for migrations only.
- **Using asyncpg instead of psycopg3:** asyncpg prepared statements break with Supabase Supavisor transaction mode. Use psycopg3 exclusively.
- **Module-level DB singleton:** Vercel functions are ephemeral. A module-level connection is recycled unpredictably. Use per-request context managers.
- **`INSERT INTO keepalive` instead of `UPDATE`:** The table should have exactly one row. Insert-based approaches can grow unbounded if the dedup logic fails. Use `UPDATE WHERE id = 1`.
- **Keeping exact version pins (`==`) for the langgraph ecosystem:** Exact pins create irresolvable conflicts when upgrading. Use `>=` minimums; let pip resolve the compatible set.

---

## Schema Migration SQL

Run once against the **direct connection** (port 5432) via Supabase SQL editor or Supabase MCP `apply_migration`. The SQL is idempotent (`IF NOT EXISTS`).

```sql
-- migration.sql
-- Enable pgvector (pre-installed on Supabase; just needs enabling)
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: tracks uploaded files per session
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    filename    TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    byte_size   INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS documents_session_idx ON documents (session_id);

-- Document chunks: text + embedding storage for RAG (Phase 3)
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    session_id   TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(768),        -- gemini-embedding-001 with output_dimensionality=768
    token_count  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS chunks_session_idx  ON document_chunks (session_id);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON document_chunks (document_id);

-- HNSW index on embedding column (cosine distance for semantic similarity)
-- Create AFTER table, before or after data (HNSW works either way)
-- m=16, ef_construction=64 are the pgvector defaults; fine for <10K vectors
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Traces table: persisted agent run traces for observability (Phase 4)
CREATE TABLE IF NOT EXISTS traces (
    run_id      TEXT PRIMARY KEY,
    thread_id   TEXT,
    query       TEXT,
    steps       JSONB,
    final_answer TEXT,
    status      TEXT,
    usage       JSONB,
    elapsed_ms  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS traces_thread_idx  ON traces (thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS traces_created_idx ON traces (created_at DESC);

-- Keepalive table: single-row ping target for Vercel cron
CREATE TABLE IF NOT EXISTS keepalive (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    pinged_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Seed with the single row (idempotent)
INSERT INTO keepalive (id, pinged_at)
VALUES (1, NOW())
ON CONFLICT (id) DO NOTHING;

-- Enforce single-row constraint (belt-and-suspenders)
CREATE UNIQUE INDEX IF NOT EXISTS keepalive_singleton ON keepalive (id);
```

**Notes on schema decisions:**
- `document_chunks.embedding` is `vector(768)`: matches `gemini-embedding-001` output with `output_dimensionality=768` (MRL truncation). RAG-02 specifies 768 dims.
- `traces.steps` is `JSONB`: the existing `Step` TypedDict serializes cleanly to JSON. No schema migration needed when new step types are added (Phase 4 concern).
- `keepalive` uses a synthetic primary key `id=1` and `ON CONFLICT DO NOTHING` for idempotent seeding. The cron uses `UPDATE` not `INSERT`, so there is never a second row.
- `AsyncPostgresSaver` creates its OWN checkpoint tables (called during Phase 2 `setup()`). Do NOT pre-create them — let the library manage its schema.

---

## LangGraph Upgrade: Breaking-Change Analysis

### What changed in the project's used APIs

| API Surface | Status | Evidence |
|-------------|--------|----------|
| `from langgraph.graph import END, START, StateGraph` | UNCHANGED | Confirmed stable across 0.2.x → 1.2.x |
| `StateGraph(AgentState)` constructor | UNCHANGED | Same signature |
| `workflow.add_node(name, fn)` | UNCHANGED | Same signature |
| `workflow.add_edge(A, B)` | UNCHANGED | Same signature |
| `workflow.add_conditional_edges(node, fn, mapping)` | UNCHANGED | Web search confirmed stable |
| `workflow.compile()` | UNCHANGED | Same signature |
| `from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage` | UNCHANGED | Stable across all versions |
| `from langchain_core.tools import tool` | UNCHANGED | Stable decorator |
| `AIMessage(content=..., tool_calls=..., usage_metadata=..., response_metadata=...)` | UNCHANGED | All parameters preserved |
| `MaxIterationsError`, `AgentState`, `Step` | Project-defined, not from LangGraph | No LangGraph impact |

### What DOES change (transitive, not project source)

| Change | Affected | Mitigation |
|--------|---------|------------|
| `langchain-core` 0.3.x → 1.4.x: `example` parameter removed from `AIMessage` | NOT used by this project | No action |
| `langchain-core` 1.0: `.text()` is now a property | NOT used by this project | No action |
| `langchain` 1.x: Legacy chains moved to `langchain-classic` | NOT imported by project source | No action |
| `langchain-community` 0.4.2 adds `langchain-classic>=1.0.7` transitive dep | No project source imports from community | Pip installs automatically |
| `langchain` 1.3.x now depends on `langgraph>=1.2.5` | Means langchain drives the langgraph version now | Both require same version — consistent |
| `langsmith` 0.1.x → 0.9.x | Not imported by project source | Transitive; no action |

### Files at risk (verify these pass tests after upgrade)

- `backend/agent/graph.py`: Imports from `langgraph.graph` and `langchain_core.messages` — both stable.
- `backend/agent/llms.py`: Imports only from `langchain_core.messages` — stable.
- `backend/agent/state.py`: Imports `BaseMessage` from `langchain_core.messages` — stable.
- `backend/agent/tools.py`: Uses `@tool` decorator from `langchain_core.tools` — stable.
- `backend/tests/*.py`: Import `AIMessage`, `HumanMessage` from `langchain_core.messages` — stable.

**Risk assessment: LOW** for the existing code. The upgrade risk is in pip dependency resolution (potential conflicts from pinning other packages), not in API breakage.

### Upgrade procedure for the plan

1. Create a fresh venv (or clone the existing one) with the new requirements.
2. Run `pip install -r requirements.txt` with the updated pins.
3. Run `python -m unittest discover -s tests -v` — all 5 test modules must pass.
4. If any test fails, read the error; it is almost certainly a transitive import issue, not a LangGraph API change.
5. Once green, commit the updated `requirements.txt`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Postgres checkpoint persistence for LangGraph state | Custom checkpointer class | `langgraph-checkpoint-postgres` `AsyncPostgresSaver` | Handles table creation, serialization, thread_id scoping, concurrent access correctly |
| Prepared-statement-safe async Postgres connection | Raw asyncpg or custom pooling | `psycopg[binary]` with `prepare_threshold=None` | Only driver that disables prepared statements cleanly for PgBouncer transaction mode |
| pgvector HNSW index | Custom similarity scoring | `CREATE INDEX USING hnsw ... vector_cosine_ops` + pgvector | Handles HNSW correctly; full table scan on >5K rows is unusably slow |
| Cron keep-alive scheduler | Background thread / asyncio loop | Vercel Cron + a simple FastAPI GET route | Vercel Hobby: 100 free cron jobs; background threads are impossible on serverless |

---

## Common Pitfalls

### Pitfall 1: Using langgraph-checkpoint-postgres 2.0.x Instead of 3.1.0

**What goes wrong:** The pinned `langgraph-checkpoint==2.1.2` is compatible with `langgraph-checkpoint-postgres 2.0.25` but NOT 3.1.0. If someone installs 2.0.25 thinking it's "close enough," Phase 2 memory and Phase 3 RAG storage will silently use a different schema than documented.

**How to avoid:** Pin `langgraph-checkpoint-postgres>=3.1.0` explicitly. Let pip pull in the correct `langgraph-checkpoint>=4.1.0`.

**Warning signs:** `ImportError` on `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`; version conflicts in pip output.

### Pitfall 2: `psycopg.errors.InvalidSqlStatementName` on Supabase Pooler

**What goes wrong:** Connecting to port 6543 WITHOUT `prepare_threshold=None`. psycopg3 tries to cache prepared statements server-side; PgBouncer transaction mode routes subsequent transactions to a different backend connection that doesn't have the cached statement. Error: `InvalidSqlStatementName`.

**How to avoid:** Always pass `prepare_threshold=None` to `AsyncConnection.connect()` when connecting to the pooler URL. The `db.py` factory enforces this centrally.

**Warning signs:** `psycopg.errors.InvalidSqlStatementName` in logs; intermittent query failures that resolve on reconnect.

### Pitfall 3: Vercel Cron Not Firing Because Expression Runs More Than Once Per Day

**What goes wrong:** The old research suggested `0 0 */5 * *` (every 5 days). This expression WORKS (it fires less than once per day). But misreading the Vercel docs could lead someone to try `*/5 * * * *` (every 5 minutes) or `0 */5 * * *` (every 5 hours), which Vercel Hobby REJECTS at deploy time with: "Hobby accounts are limited to daily cron jobs."

**How to avoid:** Use `0 0 * * *` (daily) which is always safe. This runs 7x within the 7-day window, providing 6 full days of margin.

**Warning signs:** Deployment error: "Hobby accounts are limited to daily cron jobs. This cron expression would run more than once per day."

### Pitfall 4: LangGraph Upgrade Breaks Due to Conflicting Pins

**What goes wrong:** The current `requirements.txt` uses EXACT pins (`==`). Upgrading langgraph to 1.2.6 while leaving `langchain-core==0.3.63` and `langsmith==0.1.147` pinned creates irresolvable dependency conflicts that abort `pip install`.

**How to avoid:** In the updated `requirements.txt`, change ALL LangChain-ecosystem packages from `==` to `>=` with minimum constraints. Let pip resolve the exact compatible set. Pin only the non-LangChain packages that have stability-critical reasons for exact versions (e.g., `numpy==1.26.4` for the Python 3.13 wheel issue).

**Warning signs:** `pip install` exits with `ERROR: Cannot install ... because these package versions have conflicting dependencies.`

### Pitfall 5: Migration Applied to Production Before Upgrade Completes

**What goes wrong:** If someone runs the schema migration (adding `vector` extension, creating tables) before the LangGraph upgrade is verified and deployed, the app runs on mismatched code for a window. This is unlikely to break anything in Phase 1 (migration is additive), but it muddies the "what changed" analysis if tests fail.

**How to avoid:** Run the upgrade spike first (FOUND-05), verify tests pass, redeploy, then run the schema migration (FOUND-03). The migration is purely additive and idempotent, so order matters only for clarity of diagnosis.

---

## Code Examples

### AsyncPostgresSaver Setup (Phase 2 preview, but needed in Phase 1 for table creation)

```python
# Source: PyPI langgraph-checkpoint-postgres README + WebSearch confirmation
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def create_checkpointer_tables(pooler_url: str):
    """Call once at app startup (lifespan) to create LangGraph checkpoint tables.
    Idempotent — safe to call on every deploy.
    """
    async with AsyncPostgresSaver.from_conn_string(pooler_url) as checkpointer:
        await checkpointer.setup()
```

### psycopg3 Connection with Prepared Statements Disabled

```python
# Source: psycopg.org documentation + Supabase docs confirmation
import psycopg
from psycopg.rows import dict_row

async with await psycopg.AsyncConnection.connect(
    "postgresql://postgres.REF:PASS@aws-0-REGION.pooler.supabase.com:6543/postgres",
    prepare_threshold=None,   # disables prepared statements — required for transaction pooler
    autocommit=True,          # required for LangGraph checkpoint compatibility
    row_factory=dict_row,     # required for LangGraph checkpoint compatibility
) as conn:
    result = await conn.execute("SELECT 1")
```

### HNSW Index Creation (cosine distance for RAG)

```sql
-- Source: pgvector official README (github.com/pgvector/pgvector)
CREATE INDEX ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
-- m=16 (default): max connections per HNSW layer
-- ef_construction=64 (default): candidate list size during build
-- Higher ef_construction = better recall, slower build. Defaults are correct for <10K vectors.
-- vector_cosine_ops: cosine distance (1 - cosine similarity) — correct for semantic search
```

### Vercel Cron Config

```json
{
  "crons": [
    {
      "path": "/api/keepalive",
      "schedule": "0 0 * * *"
    }
  ]
}
```

### Environment Variables (add to .env.example)

```bash
# Supabase — get from Supabase dashboard → Project Settings → Database
# Transaction Pooler (port 6543) — use for ALL application queries
SUPABASE_POOLER_URL=postgresql://postgres.PROJECTREF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres

# Direct connection (port 5432) — use ONLY for schema migrations
SUPABASE_DIRECT_URL=postgresql://postgres:PASSWORD@db.PROJECTREF.supabase.co:5432/postgres

# Vercel Cron Security — set in Vercel dashboard; Vercel sends as Bearer token
CRON_SECRET=<random-32-char-string>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| langgraph 0.2.x standalone | langchain 1.3.x includes langgraph as core dep | langchain 1.3.0 (2026) | You can no longer pin langchain 0.3.x independently; the ecosystem upgrades together |
| langgraph-checkpoint 2.x (with langgraph 0.2.x) | langgraph-checkpoint 4.x (with langgraph 1.x) | langgraph 1.2.0 (2026) | Major schema and API changes in checkpoint; must use checkpoint-postgres 3.x |
| "1 cron job per Vercel Hobby project" | 100 cron jobs, once-per-day minimum | Updated Vercel docs 2026 | Project research STACK.md was wrong; this is a capacity improvement |
| SSE MCP transport | Streamable HTTP MCP transport | MCP spec Dec 2025 | SSE deprecated; all future MCP work uses HTTP |

**Deprecated/outdated in project research:**
- STACK.md says "Vercel cron jobs: 1 per project on Hobby plan" — INCORRECT. Current: 100 per project.
- Earlier research said "langgraph >=0.3 minimum" — INCORRECT. Actual minimum for checkpoint-postgres 3.1.0 is langgraph >=1.2.0 (via checkpoint 4.x chain).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | None — uses `python -m unittest discover` |
| Quick run command | `cd backend && python -m unittest discover -s tests -v` |
| Full suite command | Same (all 5 test modules run together) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Exists? |
|--------|----------|-----------|-------------------|---------|
| FOUND-05 | Existing unit tests pass on upgraded langgraph | Regression | `python -m unittest discover -s tests -v` (5 modules) | YES — existing tests |
| FOUND-02 | Backend connects to Supabase pooler without errors | Integration / smoke | `python -c "import asyncio; from agent.db import pooler_connection; asyncio.run(verify())"` | NO — Wave 0 gap |
| FOUND-01 | pgvector extension and env vars present | Smoke | `python -c "from agent.db import pooler_connection; ..."` + SELECT query | NO — Wave 0 gap |
| FOUND-03 | All 4 tables + HNSW index exist post-migration | Schema check | SQL: `SELECT tablename FROM pg_tables WHERE tablename IN (...)` | NO — Wave 0 gap |
| FOUND-04 | Cron endpoint writes a timestamp when called with correct token | Integration | `curl -H "Authorization: Bearer $CRON_SECRET" http://localhost:8000/api/keepalive` | NO — Wave 0 gap |

### Observable Validation for Each Success Criterion

1. **Backend connects to Supabase via Transaction Pooler without errors:**
   Observable: `SELECT NOW()` via `pooler_connection()` returns a timestamp without `InvalidSqlStatementName` or `too many clients` errors.
   Command: One-shot async script → `asyncio.run(verify())` where `verify()` opens `pooler_connection()` and executes `SELECT 1`.

2. **All 4 tables + HNSW index exist after migration:**
   Observable: Supabase SQL editor query confirms tables and index.
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname = 'public'
     AND tablename IN ('documents', 'document_chunks', 'traces', 'keepalive');
   -- Should return 4 rows
   SELECT indexname FROM pg_indexes WHERE indexname = 'chunks_embedding_hnsw_idx';
   -- Should return 1 row
   ```

3. **Cron writes a fresh timestamp at least every 5 days:**
   Observable: After manual cron trigger or `curl -H "Authorization: Bearer $CRON_SECRET" https://your-app.vercel.app/api/keepalive`, Supabase SQL `SELECT pinged_at FROM keepalive WHERE id = 1` shows a timestamp within the last 24 hours.

4. **Existing backend unit tests pass on upgraded LangGraph:**
   Observable: `python -m unittest discover -s tests -v` exits 0 with all tests marked OK.
   This is the HARD GATE — no persistence code should be written until this passes.

### Sampling Rate

- **Per task commit:** `python -m unittest discover -s tests -v` (FOUND-05 gate only)
- **Per wave merge:** Full suite + manual cron trigger + Supabase table check
- **Phase gate:** All 4 success criteria verifiably TRUE before moving to Phase 2

### Wave 0 Gaps

- [ ] `backend/agent/db.py` — connection factory (new file)
- [ ] Supabase connection smoke test script (`scripts/verify_db.py` or inline in plan)
- [ ] `migration.sql` applied to Supabase project
- [ ] `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` added to Vercel env

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in Phase 1 |
| V3 Session Management | No | No sessions in Phase 1 |
| V4 Access Control | Partial | Cron endpoint uses `CRON_SECRET` Bearer token to prevent unauthorized DB writes |
| V5 Input Validation | No | No user input reaches Phase 1 endpoints |
| V6 Cryptography | No | No crypto in Phase 1 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized keepalive calls triggering DB load | Tampering | `CRON_SECRET` Bearer token check at FastAPI route level |
| Supabase service role key exposed to client | Elevation of Privilege | Service role key backend-only; never in frontend bundle; use `SUPABASE_POOLER_URL` only |
| Connection exhaustion via direct URL (5432) | Denial of Service | Use port 6543 pooler for all app queries; 5432 only in one-off migration scripts |
| Schema injection via migration SQL | Tampering | Migration runs outside app code (Supabase MCP or dashboard SQL editor), not via user input |

**Invariants from CLAUDE.md that Phase 1 must NOT violate:**
- `python_executor` security boundaries unchanged (no DB calls touch executor)
- Global secret redaction via `redaction.py` must cover new `SUPABASE_POOLER_URL` and `SUPABASE_DIRECT_URL` values (add them to the secrets list)
- No new LangSmith/external trace backend enabled (`LANGCHAIN_TRACING_V2` must NOT be set in Vercel env)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | LangGraph 1.0 "no breaking changes" claim from official blog means the existing StateGraph code will work without source modifications | LangGraph Upgrade | Low: The specific APIs used (StateGraph, add_conditional_edges, compile) are explicitly stable per web search; risk is a false positive |
| A2 | Supabase free tier "pauses after 7 days of inactivity" and a DB write counts as activity | Keep-alive cron | Medium: Supabase pricing page says "1 week," but specific definition of "inactivity" is undocumented. DB write is the most conservative correct interpretation. |
| A3 | `psycopg.errors.InvalidSqlStatementName` is the specific error from using port 6543 without `prepare_threshold=None` | Connection pattern | Low: Error class confirmed by psycopg GitHub issue #1151 and community documentation |
| A4 | `CRON_SECRET` is automatically sent as `Authorization: Bearer <value>` by Vercel on each cron invocation | Keep-alive auth | LOW: Confirmed verbatim from official Vercel docs (last_updated: 2026-06-02) |

---

## Open Questions

1. **Are there existing `langgraph-checkpoint` tables in the Supabase project?**
   - What we know: The Supabase project may or may not already exist. The research was done without checking the actual Supabase project state.
   - What's unclear: If someone ran `AsyncPostgresSaver.setup()` previously, there may be checkpoint tables. These will not conflict with our migration (additive).
   - Recommendation: Check via Supabase dashboard before running migration. If checkpoint tables exist, the migration script is still safe (all `IF NOT EXISTS`).

2. **Does `langchain-community 0.4.2` pull in `langchain-classic` which conflicts with anything?**
   - What we know: `langchain-community 0.4.2` requires `langchain-classic>=1.0.7`, a new package.
   - What's unclear: Whether `langchain-classic` conflicts with other existing dependencies.
   - Recommendation: The upgrade spike (FOUND-05) will surface this immediately via `pip install`. If conflicts occur, drop `langchain-community` from requirements if it's not used by project source (it's not — grep confirmed no `langchain_community` imports).

3. **What is the exact `SUPABASE_POOLER_URL` format for this project's Supabase region?**
   - What we know: Format is `postgresql://postgres.PROJECTREF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres`.
   - What's unclear: Region and project ref until the Supabase project is actually provisioned.
   - Recommendation: User must create the Supabase project and copy both URLs from the dashboard (Settings → Database → Connection strings).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 / 3.12 | LangGraph 1.x (requires >=3.10) | Assumed YES | 3.11 or 3.12 | No fallback; Python 3.14 has no numpy 1.26.4 wheel |
| pip | Package installation | YES | via uv or pip | — |
| Supabase project (free tier) | FOUND-01 through FOUND-04 | Unknown — must be provisioned | — | No fallback; core requirement |
| Vercel account (Hobby) | FOUND-04 (cron) | Assumed YES (currently deployed) | — | — |
| `SUPABASE_POOLER_URL` env var | FOUND-02 | NO — must be wired | — | Phase blocks without it |
| `SUPABASE_DIRECT_URL` env var | FOUND-03 (migration) | NO — must be wired | — | Migration blocks without it |
| `CRON_SECRET` env var | FOUND-04 | NO — must be generated and set | — | Cron runs unsecured without it |

**Missing dependencies with no fallback:**
- Supabase project provisioned (user must create or confirm existing project)
- `SUPABASE_POOLER_URL` in Vercel env
- `SUPABASE_DIRECT_URL` locally for migration

---

## Sources

### Primary (HIGH confidence — confirmed via official docs or verified tool output)

- PyPI registry `pip index versions` and wheel inspection — exact versions and dependency chains for all packages [VERIFIED: pypi registry]
- Vercel official docs (last_updated: 2026-06-16, 2026-06-02) — cron job constraints, CRON_SECRET mechanism, Hobby plan limits [VERIFIED: docs.vercel.com]
- pgvector official README (github.com/pgvector/pgvector) — HNSW syntax, m and ef_construction defaults [VERIFIED: github.com/pgvector/pgvector]
- Supabase pricing page — free tier: 500 MB, 7-day inactivity pause, 60 direct / 200 pooler connections [CITED: supabase.com/pricing]

### Secondary (MEDIUM confidence — official docs, some redirects or paywalls)

- Supabase connecting-to-postgres doc — Transaction Pooler port 6543 connection string format, "prepared statements not supported in transaction mode" [CITED: supabase.com/docs]
- LangGraph 1.0 blog / release policy docs — "no breaking changes" claim for LangGraph 1.0 [CITED: langchain.com/blog, docs.langchain.com/oss/python/release-policy]
- WebSearch on `psycopg3 prepare_threshold pgbouncer transaction mode` — confirmed `prepare_threshold=None` pattern [CITED: psycopg.org/psycopg3/docs]
- langchain-mcp-adapters PyPI README / wheel metadata — version requirements [VERIFIED: pypi registry]

### Tertiary (LOW confidence — training knowledge or community sources)

- "Supabase inactivity = no SQL queries" definition — community documentation; official page unavailable [ASSUMED]
- `autocommit=True` and `row_factory=dict_row` requirements for `AsyncPostgresSaver` — from PyPI README summary, not directly verified against current 3.1.0 source [ASSUMED: verify during implementation]

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| LangGraph version chain | HIGH | Verified via PyPI wheel inspection for every package in the chain |
| LangGraph API stability | MEDIUM | Official claim is "no breaking changes"; actual test-run not yet done |
| psycopg3 prepare_threshold pattern | MEDIUM | Confirmed via psycopg docs and community; `autocommit=True` needs smoke test |
| Vercel cron constraints | HIGH | Verified from official Vercel docs, last updated 2026-06-16 |
| Supabase connection limits | MEDIUM | Pricing page confirmed 60 direct / 200 pooler; inactivity definition [ASSUMED] |
| pgvector HNSW syntax | HIGH | Verified from official pgvector README |
| Schema column design | MEDIUM | Phase 1 columns are minimal and safe; downstream pillars may add columns via ALTER TABLE |

**Research date:** 2026-06-29
**Valid until:** 2026-08-01 (30 days — LangGraph ecosystem moves fast; re-verify versions at implementation time)
