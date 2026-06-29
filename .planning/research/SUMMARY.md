# Project Research Summary

**Project:** ReAct Agent - Milestone 2: Memory + RAG + MCP + Observability
**Domain:** Free-tier serverless AI agent portfolio - LangGraph / FastAPI / Vercel / Supabase
**Researched:** 2026-06-29
**Confidence:** MEDIUM

---

## Executive Summary

This milestone extends an existing, deployed ReAct agent with four engineering pillars: long-term
memory, RAG over uploaded documents, MCP tooling, and persistent observability, all on $0 spend.
The architectural driver for every pillar is the same: the backend runs on Vercel serverless
(ephemeral filesystem, no long-lived processes), so all persistence must route through an external
database. Supabase (Postgres + pgvector on the free plan) is the correct single choice: it unifies
memory checkpoints, vector storage, trace history, and keep-alive state in one service, avoiding a
proliferating set of niche free-tier tools. The free-tier constraint is itself the portfolio signal
- operating a resilient agent within hard quota limits demonstrates seniority-level cost and
reliability thinking.

The recommended implementation order is strictly sequential: Foundation then Memory then RAG then
Observability then MCP. Each phase has hard dependencies on the previous one. The single most
important pre-condition - Supabase keep-alive via a Vercel cron job - is not a feature; it is
infrastructure that prevents the live demo from dying silently after seven idle days. It must ship
on day one of Foundation, before any other code.

The two sharpest implementation risks are: (1) LangGraph version incompatibility - the existing
langgraph 0.2.45 is likely incompatible with langgraph-checkpoint-postgres 3.1.0, and this
upgrade must be resolved as the very first implementation task before any persistence code is
written; and (2) Gemini embedding rate limits - the gemini-embedding-001 free quota (~100 RPM /
~1000 RPD at project level) is shared between RAG ingestion and memory writes, requiring batching,
exponential backoff, and enforced upload size caps. Both risks are contained if caught early.

---

## Key Findings

### Recommended Stack

The additive stack is minimal by design. Supabase replaces no existing dependency - it adds
persistence. The connection layer uses psycopg[binary] >=3.2 (not asyncpg) because Supabase
Supavisor runs in transaction-pooler mode on port 6543, which breaks asyncpg prepared statements;
psycopg3 disables them cleanly via prepare_threshold=None. LangGraph persistence uses
langgraph-checkpoint-postgres >=3.1.0, providing AsyncPostgresSaver (thread-scoped checkpoint)
and PostgresStore (cross-thread long-term memory). Embeddings use gemini-embedding-001 via
langchain-google-genai >=2.0, generating 768-dimensional vectors via output_dimensionality=768
(MRL truncation from the native 3072). Vector search uses the vecs client against Supabase
pgvector with an HNSW index. Document parsing uses pymupdf4llm (0.12s/doc, clean Markdown,
Vercel-safe). MCP uses fastmcp >=2.0 (Streamable HTTP server) and langchain-mcp-adapters >=0.1.
Observability stores traces to Supabase as JSONB; Langfuse cloud (50k units/month free) is
optional but must NOT be the default - local persistence only to avoid data leakage per the
LangSmith CVE AgentSmith precedent.

**Core technologies:**
- psycopg[binary] >=3.2 + psycopg-pool: async Postgres driver - only driver compatible with
  Supabase transaction-pooler (prepare_threshold=None mandatory; use port 6543 not 5432)
- langgraph-checkpoint-postgres >=3.1.0: LangGraph-native memory - PostgresSaver (short-term)
  + PostgresStore (long-term); requires LangGraph upgrade from 0.2.45 first
- gemini-embedding-001 via langchain-google-genai >=2.0: free embeddings - 768 dims via
  output_dimensionality; shared quota budget demands batching discipline
- vecs >=0.4: Supabase pgvector client - HNSW index, filtered similarity search
- pymupdf4llm >=0.0.17: PDF parsing - 0.12s/doc, Vercel-safe, no heavy system deps
- fastmcp >=2.0 + langchain-mcp-adapters >=0.1: MCP layer - Streamable HTTP only; SSE
  deprecated Dec 2025, stdio impossible on serverless
- langfuse >=4.12.0: optional LLM-native tracing - 50k units/month free; SDK v4 import:
  from langfuse.langchain import CallbackHandler; disabled by default in production

**Critical version constraint:** mcp >=1.6 and langgraph >=0.3 are required by
langchain-mcp-adapters. This drives the LangGraph upgrade and is the first dependency to resolve.

---

### Expected Features

Features are evaluated through the lens of a recruiter evaluating the live demo in under two
minutes. The defining differentiator across all pillars is making the agent internal reasoning
legible: memory_read, document_search, and MCP tool calls must appear as named steps in the
reasoning trace panel - not as silent pipeline steps.

**Must have (table stakes):**
- Cross-session recall with agent referencing stored facts
- memory_read and memory_write visible as tool steps in the reasoning panel
- Session ID visible in UI (copyable, explains the mechanism without auth)
- Memory clear/reset button (prevents demo pollution between sessions)
- File upload (PDF + plain text) with ingestion progress feedback
- Document list per session with chunk count
- document_search tool visible in reasoning trace with source citations (filename + chunk index)
- Persistent trace history: list of recent runs, clickable, per-step with elapsed_ms
- Provider used per run + fallback events displayed
- Supabase keep-alive cron (prevents 7-day pause from killing the demo)
- At least one MCP tool call visible in reasoning trace from a real (non-toy) MCP tool

**Should have (differentiators):**
- Semantic memory retrieval via pgvector (strongest LLM/ML signal in the memory pillar)
- Memory type distinction (memory_type column: fact vs. preference vs. event)
- Chunk-level citation with cosine similarity score
- Ingestion pipeline stats in UI (chunk count, embedding model, avg chunk length)
- Free-tier quota visualization dashboard (Gemini RPD usage vs. known limits)
- Eval trend over time (multiple baseline snapshots stored in Supabase)
- MCP dynamic tool discovery (tools/list at startup, not hardcoded)
- Graceful "not found in documents" handling

**Defer to v2+:**
- Per-memory editing UI; auth-gated memory; OCR for scanned PDFs
- Web URL ingestion; semantic chunking; reranking; multi-agent orchestration
- Self-hosted Langfuse; MCP resource/prompt primitives; OpenTelemetry full instrumentation

---

### Architecture Approach

The extended system adds four new backend modules (db.py, memory.py, documents.py,
mcp_adapter.py) and three new frontend components (TracesDashboard, DocUploadPanel, MemoryBadge)
while making minimal changes to the existing graph.py and api.py. The connection layer (db.py)
is the single import point for all Supabase access. Key architectural decisions: (1) RAG
retrieval is a registered LangGraph tool (retrieve_context), not a pipeline pre-step, preserving
the existing tool-selection ethos and making retrieval visible in the reasoning trace; (2) trace
persistence is fire-and-forget (asyncio.create_task) after the SSE stream closes, keeping it off
the critical path; (3) thread_id equals session_id and flows as HTTP header X-Session-Id from
localStorage, requiring no auth; (4) every Supabase connection opens and closes per request via
context manager - no module-level singleton - because Vercel functions are ephemeral.

**Major components:**
1. backend/agent/db.py (new) - shared connection factory: pooler URI for queries (port 6543,
   prepare_threshold=None), direct URI for migrations only (port 5432)
2. backend/agent/memory.py (new) - load_memory_block() (pre-graph, injects into system prompt)
   + save_memory_facts() (post-graph, writes salient facts to PostgresStore)
3. backend/agent/documents.py (new) - upload handler: extract then chunk (800 chars, 100-char
   overlap, paragraph-first) then batch embed (Gemini, 5 chunks/batch) then upsert pgvector
4. retrieve_context tool in backend/agent/tools.py (addition) - pgvector filtered similarity
   search via Supabase stored procedure match_chunks(); appears in reasoning trace like all tools
5. backend/agent/mcp_adapter.py (new) - MultiServerMCPClient with Streamable HTTP; returns []
   if no MCP server URL configured; merged into build_graph() at call time
6. TracesDashboard.tsx + DocUploadPanel.tsx (new frontend) - consume GET /api/traces and
   POST /api/documents/upload

**Supabase schema (application tables - PostgresSaver creates checkpoint tables automatically):**
- documents (id, session_id, filename, mime_type, byte_size, created_at)
- document_chunks (id, document_id, session_id, chunk_index, content, embedding vector(768),
  token_count, created_at) + HNSW index (cosine distance)
- traces (run_id, thread_id, query, steps jsonb, final_answer, status, usage jsonb,
  elapsed_ms, created_at)
- keepalive (id, pinged_at) - single-row ping target for the Vercel cron

---

### Critical Pitfalls

All four researchers independently flagged the same five risks. Ordered by severity to the live demo.

1. **Supabase 7-day inactivity pause** - implement the Vercel cron keep-alive (every 5 days,
   pinging /api/health which touches the keepalive table) on day one of Foundation. Dashboard
   visits do not count as database activity. A paused Supabase means a 30-second blank screen
   for a recruiter. This is a Foundation pre-condition, not a feature.

2. **LangGraph version incompatibility** - langgraph 0.2.45 is likely incompatible with
   langgraph-checkpoint-postgres 3.1.0 (which requires langgraph >=0.3, itself required by
   langchain-mcp-adapters). Must be resolved as the first implementation task.

3. **Supabase connection exhaustion via direct URL** - use port 6543 (Transaction Pooler) with
   prepare_threshold=None for all application queries. Port 5432 is for migrations only. Free
   tier allows ~60-100 direct connections; Vercel serverless exhausts this under trivial load.

4. **Prompt injection via uploaded documents** - PDFs can contain invisible text with embedded
   instructions (OWASP LLM01:2025). Mitigation: instruction barrier prepended to retrieved chunks
   in the system prompt; strip zero-width chars during ingestion; scope retrieval strictly to the
   uploading session. Do not weaken python_executor security boundaries.

5. **Gemini embedding rate-limit exhaustion during ingestion** - ~1000 RPD shared between RAG
   ingestion and memory writes. Batch via embed_documents() not per-chunk loops; enforce upload
   size limits (5-10 MB, 10-20 pages); apply tenacity exponential backoff on 429 responses; run
   ingestion async (job ID + polling) to avoid Vercel function timeout.

---

## Implications for Roadmap

Build order is strictly sequential. Each phase has hard dependencies on all preceding phases.
Do not parallelize.

### Phase 1: Foundation

**Rationale:** Every subsequent pillar imports from db.py and requires Supabase tables to exist.
The keep-alive cron is the single most important reliability mechanism. The LangGraph upgrade
must be resolved here to unblock all persistence code.

**Delivers:**
- Supabase project provisioned, pgvector enabled, env vars set in Vercel + .env.example
- backend/agent/db.py with connection factory (pooler port 6543, prepare_threshold=None;
  direct port 5432 for migrations only)
- Schema migration (documents, document_chunks, traces, keepalive tables + HNSW index)
- PostgresSaver.setup() called in api.py lifespan (idempotent)
- Vercel cron keep-alive: /api/health touches keepalive table every 5 days
- LangGraph version upgrade resolved and pinned (langgraph >=0.3)

**Addresses pitfalls:** Supabase pause, connection exhaustion, LangGraph version incompatibility

**Research flag:** Run the LangGraph upgrade as a spike before planning this phase - it is the
hard blocker for everything downstream.

### Phase 2: Memory

**Rationale:** Memory adds session_id to AgentState, which RAG (Phase 3) depends on for
session-scoped document retrieval. The PostgresSaver checkpointer modifies build_graph() - RAG
and MCP also touch build_graph(), so memory changes must be stable first.

**Delivers:**
- Frontend sends X-Session-Id header on every /api/run request
- backend/api.py extracts thread_id, passes to build_graph(checkpointer=...)
- backend/agent/memory.py: load_memory_block() (pre-graph) + save_memory_facts() (post-graph)
- backend/agent/state.py: session_id field added to AgentState
- memory_read and memory_write as registered agent tools (appear in reasoning trace)
- Session ID visible in UI; memory clear button
- Memory cap: top-10 by recency; category-keyed upsert for mutable facts

**Implements:** PostgresSaver (short-term), PostgresStore (long-term), pre/post-graph hooks

**Avoids:** Storing full message history in long-term store; unbounded memory growth

### Phase 3: RAG

**Rationale:** RAG depends on session_id in AgentState (added Phase 2) to scope vector search
to the uploading session. The ingestion pipeline is the most complex and rate-limit-sensitive
component; it should be built with the database connection layer and session architecture stable.

**Delivers:**
- backend/agent/documents.py: upload handler with batching (5 chunks/batch), tenacity backoff,
  upload size cap (5 MB / 20 pages), ingestion progress feedback
- POST /api/documents/upload + GET /api/documents routes (bare + /api/-prefixed per codebase
  convention from CLAUDE.md)
- match_chunks() stored procedure migration in Supabase
- retrieve_context tool in backend/agent/tools.py + TOOL_SCHEMAS with directive description
- DocUploadPanel.tsx: file input, ingestion progress, document list with chunk count
- Source citations in agent responses (filename + chunk index + similarity score)
- Instruction barrier in system prompt for retrieved chunks
- Ingestion idempotency by content hash

**Avoids:** Naive fixed-size character chunking; synchronous ingestion; per-chunk embed_query()
loops; prompt injection

**Research flag:** Verify actual Gemini embedding RPM/RPD limits in Google AI Studio before
finalizing batch sizes.

### Phase 4: Observability

**Rationale:** Trace persistence is purely additive - one fire-and-forget write after the SSE
stream, one new read endpoint. Building it after RAG means dashboard traces include RAG retrieval
steps, which is more legible to a recruiter.

**Delivers:**
- asyncio.create_task(persist_trace(...)) in api.py after final SSE event (non-blocking)
- GET /api/traces?limit=20&offset=0 reading from Supabase
- TracesDashboard.tsx: timeline of recent runs, per-step expansion with elapsed_ms,
  provider + fallback events, token/cost per run
- In-memory RUNS dict retained as write-through cache for backwards compatibility
- Langfuse cloud as opt-in via env vars; disabled by default
- No LANGCHAIN_TRACING_V2=true in Vercel environment (local persistence only)

**Avoids:** Secret leakage via external trace SaaS (LangSmith CVE AgentSmith precedent)

### Phase 5: MCP

**Rationale:** MCP is the most architecturally isolated pillar - disabled entirely by leaving
MCP_FETCH_SERVER_URL unset. It modifies build_graph() but introduces no new database
dependencies. Placed last because graph architecture must be stable before adding the most
protocol-edge-case-prone component.

**Delivers:**
- backend/agent/mcp_adapter.py: MultiServerMCPClient with Streamable HTTP transport; returns []
  if no URL configured (graceful degradation)
- build_graph(mcp_tools=[...], checkpointer=...) merges MCP tools with native tools at call time
- Companion MCP server (fastmcp, mounted at /mcp on existing FastAPI app) with 1-2 real tools
- MCP tools dynamically discovered via tools/list at startup (not hardcoded)
- MCP tool calls appear in reasoning trace identically to native tool calls
- README diagram of MCP architecture
- MCP_FETCH_SERVER_URL env var; empty = MCP disabled

**Avoids:** stdio transport (impossible on Vercel); SSE transport (deprecated Dec 2025); NIH
protocol implementation (use official mcp SDK)

**Research flag:** MCP Streamable HTTP spec finalized June 2026; pin fastmcp and
langchain-mcp-adapters versions tightly; allocate extra time for protocol edge cases.

---

### Phase Ordering Rationale

- Foundation first: db.py is imported by all four subsequent modules; keep-alive cron has zero
  feature dependencies and prevents the most visible demo failure
- Memory before RAG: session_id in AgentState is required by the RAG retrieval tool;
  build_graph() signature change must be stable before RAG adds tools
- RAG before Observability: observability is additive; traces become more interesting after RAG
  steps appear in them
- Observability before MCP: purely additive, no blast radius; MCP modifies graph build and is
  the highest protocol-risk component
- MCP last: env-var toggle, no database dependencies, highest novelty risk - independently
  verifiable in isolation

### Research Flags

**Needs spike before planning:**
- Phase 1: LangGraph upgrade path - run pip install langgraph-checkpoint-postgres
  langchain-mcp-adapters against current requirements.txt; resolve conflicts before Phase 1 plan.
  This is the hard blocker.
- Phase 3: Gemini embedding actual rate limits - verify RPM/RPD in Google AI Studio before
  finalizing ingestion batch strategy.
- Phase 5: MCP Streamable HTTP edge cases - pin package versions tightly; allocate extra time.

**Standard patterns (no extra research needed):**
- Phase 2: PostgresSaver + PostgresStore well-documented in LangGraph official docs; version risk
  resolved in Phase 1.
- Phase 4: Fire-and-forget asyncio.create_task + Supabase JSONB insert is trivial; dashboard
  follows existing component patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Library choices confirmed via official docs and community; LangGraph version pin is LOW confidence until tested; Gemini rate limits are approximate |
| Features | HIGH | Audience known, constraints known, existing system known; decisions are engineering judgment calls with no market uncertainty |
| Architecture | MEDIUM | Integration patterns confirmed via LangGraph docs, Supabase docs, MCP spec; psycopg3 prepare_threshold=None needs smoke-testing |
| Pitfalls | MEDIUM | All five critical pitfalls corroborated across multiple independent sources; rate-limit numbers are point-in-time |

**Overall confidence: MEDIUM**

The research is coherent and internally consistent across all four researchers. Main uncertainty is
in version compatibility (LangGraph upgrade) and embedding rate limits - both resolvable with a
short spike before Phase 2 planning.

### Gaps to Address

- **LangGraph upgrade path (BLOCKER):** Run pip install langgraph-checkpoint-postgres
  langchain-mcp-adapters against current requirements.txt; resolve conflicts before Phase 1
  planning is finalized. This gates all persistence code.
- **Gemini embedding rate limits (verify before Phase 3 planning):** Check actual RPM and RPD
  in Google AI Studio. The research estimate (~100 RPM / ~1000 RPD) is LOW confidence.
- **Async vs. sync ingestion decision (Phase 3):** Synchronous with hard page cap (simpler) or
  async with job ID + polling (correct for larger docs). Async adds a status endpoint and
  frontend polling logic.
- **MCP companion server tool selection (Phase 5):** Decide which 1-2 tools the companion server
  exposes before Phase 5 planning. Must be real tools, not toy echo.

---

## Sources

### Primary (used to make architectural decisions)
- Supabase Docs - Connecting to Postgres (Transaction Pooler port 6543, prepared statement disable)
- LangGraph Docs - PostgresSaver, PostgresStore, thread_id config, pre/post-graph memory hooks
- MCP Spec 2025-03-26 - Streamable HTTP transport (confirmed current standard; SSE deprecated Dec 2025)
- Gemini API Docs - gemini-embedding-001, output_dimensionality=768, rate limits (approximate)

### Secondary (MEDIUM confidence)
- travisvn/supabase-pause-prevention - 7-day inactivity pause behavior and keep-alive patterns
- langchain-mcp-adapters GitHub - MultiServerMCPClient API surface
- fastmcp community - Vercel serverless deployment pattern for Streamable HTTP MCP servers
- Langfuse pricing page - 50k units/month free; SDK v4 import paths confirmed
- pgvector community - HNSW vs IVFFlat tradeoffs at small scale
- Noma Security - CVE AgentSmith (LangSmith); rationale for local-only trace persistence

### Tertiary (LOW confidence - verify before implementing)
- Gemini rate-limit numbers (~100 RPM / ~1000 RPD) - community sources, not Google official dashboard
- LangGraph version compatibility (0.2.45 to >=0.3) - inferred from package metadata; unverified against CI
- Vercel function timeout for RAG ingestion - estimated from per-step latency; needs smoke test

---

*Research completed: 2026-06-29*
*Ready for roadmap: yes*