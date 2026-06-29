---
phase: 01-foundation
plan: 03
subsystem: infra
requires: [01-02]
provides:
  - Idempotent schema migration (pgvector + 4 tables + HNSW index) authored and applied to live Supabase
  - verify_schema.py asserting the schema is live
  - RLS enabled on all 4 foundation tables (security hardening beyond plan scope)
affects: [01-04, phase-03-rag, phase-04-observability]
key-files:
  created:
    - .planning/phases/01-foundation/migration.sql
    - backend/scripts/verify_schema.py
requirements-completed: [FOUND-03, FOUND-01]
completed: 2026-06-29
status: complete
---

# Phase 1 Plan 03: Schema Migration Applied + Verified

**Authored the idempotent foundation schema, applied it to the live Supabase DB via the Supabase MCP, and verified the 4 tables + HNSW index exist — then hardened with RLS.**

## Accomplishments
- `migration.sql`: `CREATE EXTENSION IF NOT EXISTS vector`; tables `documents`, `document_chunks` (`embedding vector(768)`, FK→documents ON DELETE CASCADE), `traces`, `keepalive`; supporting btree indexes; `chunks_embedding_hnsw_idx` (`hnsw`, `vector_cosine_ops`, m=16, ef_construction=64); `keepalive` seeded id=1. All `IF NOT EXISTS` (re-runnable). No checkpoint tables (Phase 2's `AsyncPostgresSaver.setup()` owns those).
- Applied via Supabase MCP `apply_migration` (project `vvhbvldwihytvnqotmfd`) → `{"success":true}`.
- `verify_schema.py`: async assertion of the 4 tables + HNSW index via the pooler.
- **Security:** enabled RLS on all 4 tables (`ENABLE ROW LEVEL SECURITY`). The backend connects as the `postgres` table owner (RLS-bypass), so no policies are needed and the backend is unaffected; this closes the default-exposed PostgREST anon path. Confirmed backend can still read `keepalive` (1 row) with RLS on.

## Verification
- grep gates: 4 `CREATE TABLE`, 1 `USING hnsw`, 1 `CREATE EXTENSION ... vector`, 1 `vector(768)`.
- `python scripts/verify_schema.py` → `4 tables, hnsw index present`, exit 0.
- MCP `list_tables`: `documents` (0), `document_chunks` (0), `traces` (0), `keepalive` (1). **Roadmap SC2 met.**

## Deviations
- Applied via Supabase MCP (plan listed MCP / `db push` / psql as acceptable). RLS enablement is an added hardening step (Supabase critical advisory) approved by the user — not in the original plan scope.
