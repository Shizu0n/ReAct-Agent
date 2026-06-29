# Walking Skeleton — ReAct Agent: Persistence Foundation

**Phase:** 1
**Generated:** 2026-06-29

## Capability Proven End-to-End

> The smallest user-visible capability that exercises the full upgraded stack.

An operator (or Vercel cron) issues `GET /api/keepalive` with the `CRON_SECRET` bearer
token against the deployed app, and a fresh `pinged_at` timestamp lands in the live
Supabase `keepalive` table — exercising the upgraded LangGraph runtime → FastAPI route →
psycopg3 Transaction-Pooler connection → live Postgres, the exact path every later pillar
(Memory checkpointer, RAG chunks, Observability traces) will reuse.

There is no end-user UI in this phase by design (Phase 1 is pure persistence backbone).
The "user" for the Walking Skeleton is the operator/recruiter who can prove the demo's
durability: the keep-alive round-trip is the legible, end-to-end proof.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Persistence | Supabase Postgres + pgvector (free tier, 500 MB) | Already connected; unifies memory + RAG + traces in one service at $0 |
| DB driver | `psycopg[binary]` 3.x, async | Only driver that disables prepared statements cleanly (`prepare_threshold=None`) for Supabase Supavisor transaction mode |
| Connection routing | Transaction Pooler (port 6543) for ALL app queries; direct (port 5432) for migrations only | Free tier has 60 direct / 200 pooler connections; serverless cold starts exhaust 5432 fast |
| Connection lifecycle | Per-request async context manager in `backend/agent/db.py`; NO module-level singleton | Vercel functions are ephemeral; a cached connection is recycled unpredictably |
| Schema delivery | Idempotent `migration.sql` applied once via direct connection / Supabase MCP `apply_migration` | DDL runs outside app code; `IF NOT EXISTS` makes re-runs safe |
| Vector index | pgvector HNSW, `vector_cosine_ops`, m=16, ef_construction=64 | pgvector defaults; correct for the <10K-vector free-tier scale |
| Keep-alive | Vercel Cron (`0 0 * * *`, daily) → `GET /api/keepalive` → single-row `UPDATE` | Hobby allows 100 crons, daily minimum; daily fires 7× inside the 7-day pause window (6-day margin) |
| Cron auth | `CRON_SECRET` bearer-token check at the route | Vercel auto-sends `Authorization: Bearer $CRON_SECRET`; prevents unauthorized DB writes |
| Runtime baseline | LangGraph `>=1.2.6` / langchain `>=1.3.11` / langchain-core `>=1.4.8` ecosystem | Required transitively by `langgraph-checkpoint-postgres>=3.1.0`; upgrade is the hard blocker for every downstream phase |
| Secret handling | Extend `redaction.py` `SECRET_ENV_MARKERS` with `SUPABASE`; connection strings stay backend-only | Name-based redaction does NOT cover `SUPABASE_*_URL` values otherwise; the URL embeds the DB password |

## Stack Touched in Phase 1

- [x] Dependency runtime upgrade (LangGraph ecosystem) + regression gate (existing unit suite green)
- [x] Routing — one real route (`/keepalive` + `/api/keepalive`, dual-registered + `vercel.json` rewrite)
- [x] Database — one real write (`UPDATE keepalive`) AND one real read (`SELECT NOW()` smoke + schema verification queries)
- [x] DB connection layer reused by every later phase (`pooler_connection()` / `direct_connection()`)
- [x] Deployment — Vercel cron registered; deployed `/api/keepalive` round-trip confirmed (human-verify)

## Artifacts This Phase Produces

| Artifact | Kind | Plan |
|---|---|---|
| `backend/requirements.txt` (upgraded pins) | edit | 01-01 |
| `backend/agent/db.py` → `pooler_connection()`, `direct_connection()`, `_pooler_url()`, `_direct_url()` | new | 01-02 |
| `backend/agent/redaction.py` → `SECRET_ENV_MARKERS` += `"SUPABASE"` | edit | 01-02 |
| `backend/tests/test_redaction.py` → Supabase-URL redaction case | edit | 01-02 |
| `backend/.env.example` → `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` | edit (Bash append) | 01-02 |
| `backend/scripts/verify_db.py` → pooler smoke (`SELECT NOW()`) | new | 01-02 |
| `.planning/phases/01-foundation/migration.sql` | new | 01-03 |
| `documents`, `document_chunks`, `traces`, `keepalive` tables + `chunks_embedding_hnsw_idx` (live Supabase) | DB objects | 01-03 |
| `backend/api.py` → `keepalive_handler` (`/keepalive` + `/api/keepalive`), `import os` | edit | 01-04 |
| `vercel.json` → `crons[]` + `/keepalive` rewrite | edit | 01-04 |
| `backend/tests/test_api.py` → keepalive auth tests (200 / 401) | edit | 01-04 |
| New env vars: `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` | config | 01-02 / 01-04 |

## Out of Scope (Deferred to Later Slices)

> Explicit, to prevent later phases re-litigating Phase 1's minimalism.

- LangGraph `AsyncPostgresSaver.setup()` / checkpoint tables — Phase 2 (Memory) calls `setup()`; do NOT pre-create them here
- `PostgresStore` long-term memory tables — Phase 2
- Embedding generation / writing real vectors into `document_chunks.embedding` — Phase 3 (RAG)
- Writing real run traces into `traces` — Phase 4 (Observability)
- Any frontend/UI change — no end-user surface in Phase 1
- MCP packages (`langchain-mcp-adapters`, `mcp`) — only version-compatibility is future-proofed here; not installed until Phase 5

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its
architectural decisions (pooler routing, per-request connections, the four tables):

- Phase 2 (Memory): `AsyncPostgresSaver` checkpointer + `PostgresStore` over the pooler; session id header; memory steps in the trace
- Phase 3 (RAG): document upload → batch embed (Gemini 768-dim) → write `document_chunks` → pgvector HNSW retrieval → cited answers
- Phase 4 (Observability): fire-and-forget writes to `traces`; trace-history dashboard
- Phase 5 (MCP): companion MCP server over Streamable HTTP; dynamic `tools/list`
