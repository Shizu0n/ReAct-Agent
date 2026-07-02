# Roadmap: ReAct Agent — Memory + RAG + MCP + Observability

## Overview

This milestone scales an existing, deployed ReAct agent with four market-relevant engineering
pillars: long-term memory, RAG over uploaded documents, persistent observability, and MCP tooling
— all operating within free-tier quotas ($0 spend). Build order is strictly sequential; every
pillar depends on the one before it. The free-tier constraint is itself the engineering story:
operating a resilient agent within hard quota limits demonstrates seniority-level cost and
reliability thinking, which is the core recruiter-facing signal.

## Phases

- [x] **Phase 1: Foundation** — Supabase persistence backbone, DB schema, keep-alive cron, LangGraph upgrade
- [x] **Phase 2: Memory** — Cross-session conversation history and long-term fact recall with visible trace steps
- [ ] **Phase 3: RAG** — Document upload, rate-limit-safe ingestion pipeline, pgvector retrieval, cited answers
- [ ] **Phase 4: Observability** — Persistent trace history, per-step dashboard, provider and fallback display
- [ ] **Phase 5: MCP** — Companion MCP server, dynamic tool discovery via `tools/list`, env-var toggle

## Phase Details

### Phase 1: Foundation

**Goal**: The persistence backbone is operational, all four application tables are deployed, the live demo is protected from the Supabase 7-day inactivity pause, and LangGraph is upgraded so all downstream persistence code can be written without version conflicts.
**Mode:** mvp
**Depends on**: Nothing (first phase) — run LangGraph upgrade as a spike before planning; it is the hard blocker for all subsequent phases
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05
**Success Criteria** (what must be TRUE):

  1. The backend connects to Supabase via the Transaction Pooler (port 6543, prepared statements disabled) and runs a query without connection errors
  2. All four application tables (`documents`, `document_chunks`, `traces`, `keepalive`) plus the HNSW vector index exist in Supabase after running the migration
  3. The Vercel cron job writes a fresh timestamp to the `keepalive` table at least every 5 days, preventing the free-tier 7-day inactivity pause
  4. All existing backend unit tests pass on the upgraded LangGraph version (>=0.3) with no regressions

**Plans**: 4/4 plans executed (deployed keepalive round-trip verified 2026-06-29)
**Wave 1**

- [x] 01-01-PLAN.md — LangGraph ecosystem upgrade + regression gate (FOUND-05, SC4)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Supabase provisioning + pooler connection layer + redaction fix + live query smoke (FOUND-01, FOUND-02, SC1)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Schema migration authored + applied to live Supabase + verified (FOUND-01, FOUND-03, SC2)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — Keep-alive cron endpoint + Vercel cron + CRON_SECRET auth + deployed round-trip (FOUND-04, SC3)

### Phase 2: Memory

**Goal**: Users who return to the site find the agent continuing the conversation and referencing facts shared in prior sessions, with memory activity visible as discrete steps in the reasoning panel.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05, MEM-06, MEM-07
**Success Criteria** (what must be TRUE):

  1. A user who closes the browser and returns can continue their conversation without re-sending history (PostgresSaver restores from Supabase)
  2. A user who shares a personal fact in one session finds the agent referencing it naturally in a later session ("As you mentioned…") via long-term PostgresStore
  3. `memory_read` and `memory_write` appear as discrete named steps in the reasoning trace panel, not as silent pipeline operations
  4. The current session ID is visible and copyable in the UI, enabling a recruiter to verify cross-session persistence manually
  5. Clicking "clear memory" in the UI results in the agent having no recollection of prior facts in the next turn

**Plans**: 4/4 plans executed (live SC1–SC5 round-trip verified 2026-07-01)
**UI hint**: yes

**Wave 1**

- [x] 02-01-PLAN.md — Foundation: api/+root requirements sync, AsyncConnectionPool, lifespan checkpointer/store, async invocation, X-Session-Id -> thread_id, [BLOCKING] live schema setup (MEM-01, MEM-02; SC1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Long-term memory as visible tools: memory_read/memory_write in tool_node, recency cap, prompt-injection barrier (MEM-03, MEM-04, MEM-07; SC2, SC3)
- [x] 02-03-PLAN.md — Session identity + display: localStorage session id, X-Session-Id header, copyable session-id chip (MEM-01, MEM-05; SC1, SC4)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-04-PLAN.md — Clear memory: DELETE /memory/{session_id} dual route + UUID validation, vercel rewrite, UI clear wiring, full SC1–SC5 round-trip (MEM-06; SC5)

### Phase 3: RAG

**Goal**: Users can upload a document and receive accurate, cited answers grounded in its content, with the retrieval step visible in the reasoning trace and hallucinations prevented when content is not found.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: RAG-01, RAG-02, RAG-03, RAG-04, RAG-05, RAG-06, RAG-07, RAG-08, RAG-09
**Success Criteria** (what must be TRUE):

  1. A user can upload a PDF or plain-text file and see a progress indicator confirming ingestion completion with a chunk count
  2. Asking a question covered by the uploaded document returns an answer with inline citations (filename + chunk index)
  3. The `document_search` tool appears as a named step in the reasoning trace with its query and retrieved content visible
  4. Asking a question not answered by any uploaded document results in the agent explicitly acknowledging the absence rather than fabricating an answer
  5. A per-session document list in the UI shows each uploaded filename and its chunk count

**Plans**: 4 plans
**UI hint**: yes

**Wave 1**

- [x] 03-01-PLAN.md — Ingestion library: embedding.py (batch + 429 backoff) + ingest.py (extract/strip/chunk/cap/embed/insert) + pypdf legitimacy gate (RAG-01, RAG-02, RAG-04, RAG-09-ingest)

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — Upload + documents endpoints (2 MB/type guards, per-session list) + vercel.json rewrites & maxDuration:60 (RAG-01, RAG-03, RAG-04, RAG-07)

**Wave 3** *(blocked on Wave 2; 03-03 ∥ 03-04)*

- [x] 03-03-PLAN.md — Frontend upload widget + ingestion progress + per-session document list (RAG-01, RAG-03, RAG-07)
- [x] 03-04-PLAN.md — document_search tool: session-scoped pgvector retrieval, citations, no-hallucination guard, prompt-injection barrier, pool wiring (RAG-05, RAG-06, RAG-08, RAG-09-retrieve)

### Phase 4: Observability

**Goal**: Any completed run can be reviewed after the fact — full step trace with timing, provider used, fallback events — without blocking the agent response or leaking trace data to external services.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06
**Success Criteria** (what must be TRUE):

  1. A scrollable list of recent runs is visible in the UI, each showing timestamp, query summary, status, and total elapsed time
  2. Clicking a run expands its step trace showing each thought/action/observation with `elapsed_ms` per step
  3. Each run entry shows the provider used (e.g., Gemini) and any fallback events (e.g., "Gemini failed → Groq")
  4. Eval results visible in the UI match the committed `baseline.json` without requiring a manual refresh

**Plans**: TBD
**UI hint**: yes

### Phase 5: MCP

**Goal**: The agent dynamically discovers and invokes real tools from a companion MCP server via Streamable HTTP, the calls appear in the reasoning trace identically to native tool calls, and the feature degrades cleanly when the server URL is unconfigured.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05
**Success Criteria** (what must be TRUE):

  1. With `MCP_FETCH_SERVER_URL` set, the agent discovers available tools via `tools/list` and successfully invokes at least one real (non-toy) MCP tool in a live conversation
  2. An MCP tool call appears in the reasoning trace panel identically to native tool calls (same thought/action/observation structure, same visual treatment)
  3. With `MCP_FETCH_SERVER_URL` unset, the agent starts and responds normally with no error message or degraded behavior
  4. The README contains an architecture diagram of the MCP integration (agent ↔ client ↔ HTTP ↔ server)

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | ✓ Complete | 2026-06-29 |
| 2. Memory | 4/4 | ✓ Complete | 2026-07-01 |
| 3. RAG | 4/4 | Implemented (tests green); live verify pending | 2026-07-02 |
| 4. Observability | 0/? | Not started | - |
| 5. MCP | 0/? | Not started | - |
