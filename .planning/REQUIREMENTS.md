# Requirements: ReAct Agent — Memory + RAG + MCP + Observability

**Defined:** 2026-06-28
**Core Value:** A recruiter can open the live demo and, within minutes, see legible evidence of agent-engineering skill (visible reasoning, memory, document RAG, traces, evals) — all on $0 model spend.

## v1 Requirements

Requirements for this milestone. Grouped by pillar; build order is strictly sequential
(Foundation → Memory → RAG → Observability → MCP). Each maps to roadmap phases.

### Foundation (FOUND)

- [ ] **FOUND-01**: Supabase project is provisioned with pgvector enabled and required env vars wired in Vercel and `.env.example`
- [ ] **FOUND-02**: A shared DB connection layer uses the Transaction Pooler (port 6543, prepared statements disabled) for queries and the direct connection (port 5432) for migrations only
- [ ] **FOUND-03**: A schema migration creates the `documents`, `document_chunks`, `traces`, and `keepalive` tables plus an HNSW vector index
- [ ] **FOUND-04**: A scheduled keep-alive (Vercel cron) writes to the database at least every 5 days so the free-tier project never hits the 7-day inactivity pause
- [ ] **FOUND-05**: LangGraph is upgraded to a version compatible with `langgraph-checkpoint-postgres` and `langchain-mcp-adapters`, and the existing unit tests still pass

### Memory (MEM)

- [ ] **MEM-01**: The frontend sends an anonymous session id (e.g. `X-Session-Id` header) on every agent run
- [ ] **MEM-02**: Conversation history persists across browser sessions, keyed by session id (PostgresSaver checkpointer)
- [ ] **MEM-03**: The agent stores salient long-term facts and references them in later responses ("As you mentioned before…")
- [ ] **MEM-04**: Memory reads/writes appear as named steps (`memory_read`/`memory_write`) in the reasoning trace
- [ ] **MEM-05**: The current session id is visible and copyable in the UI
- [ ] **MEM-06**: The user can clear/reset all memory for the current session from the UI
- [ ] **MEM-07**: Stored memory is capped (top-N by recency) so it cannot grow unbounded

### RAG (RAG)

- [ ] **RAG-01**: The user can upload PDF and plain-text documents
- [ ] **RAG-02**: Ingestion extracts text, chunks it, batch-embeds via `gemini-embedding-001` (768-dim), and stores chunks in pgvector
- [ ] **RAG-03**: Ingestion shows progress feedback in the UI (status + chunk count)
- [ ] **RAG-04**: Ingestion handles embedding rate limits (batching + exponential backoff) and enforces an upload size cap
- [ ] **RAG-05**: A `document_search` tool retrieves session-scoped chunks and appears as a step in the reasoning trace
- [ ] **RAG-06**: Agent answers include source citations (filename + chunk index)
- [ ] **RAG-07**: A per-session document list shows uploaded files with chunk counts
- [ ] **RAG-08**: When retrieved chunks do not answer the question, the agent says so instead of hallucinating
- [ ] **RAG-09**: Retrieved document content is isolated by a prompt-injection barrier in the system prompt, and ingestion strips zero-width/invisible characters

### Observability (OBS)

- [ ] **OBS-01**: Completed runs are persisted to Supabase without blocking the response (fire-and-forget)
- [ ] **OBS-02**: The UI shows a list of recent runs (clickable trace history)
- [ ] **OBS-03**: A trace detail view shows each step with its elapsed time (`elapsed_ms`)
- [ ] **OBS-04**: Each run displays the provider used and any fallback events (e.g. "Gemini failed → Groq")
- [ ] **OBS-05**: Eval results surfaced in the UI reflect the current committed baseline
- [ ] **OBS-06**: Traces are stored locally (Supabase) only; no external trace SaaS is enabled by default and existing secret redaction is preserved

### MCP (MCP)

- [ ] **MCP-01**: A companion MCP server (Streamable HTTP transport) exposes at least one real, non-toy tool
- [ ] **MCP-02**: The agent consumes the MCP server and discovers its tools dynamically (`tools/list`), not hardcoded
- [ ] **MCP-03**: MCP tool calls appear in the reasoning trace identically to native tool calls
- [ ] **MCP-04**: MCP can be disabled cleanly via an env var (graceful degradation when unset)
- [ ] **MCP-05**: The README documents the MCP architecture (agent ↔ client ↔ HTTP ↔ server)

## v2 Requirements

Deferred to a future milestone. Tracked but not in the current roadmap.

### Memory

- **MEM-V2-01**: Semantic memory retrieval via pgvector similarity (not just recency)
- **MEM-V2-02**: Memory type distinction (fact vs. preference vs. event) with weighted retrieval

### RAG

- **RAG-V2-01**: Chunk-level citations include cosine similarity score in the UI
- **RAG-V2-02**: Ingestion pipeline stats in UI (embedding model, avg chunk length)
- **RAG-V2-03**: Drag-and-drop upload and additional file formats

### Observability

- **OBS-V2-01**: Free-tier quota visualization (usage vs. known Gemini/Groq limits)
- **OBS-V2-02**: Eval trend over time (multiple baseline snapshots stored with timestamps)
- **OBS-V2-03**: Provider health / fallback timeline view
- **OBS-V2-04**: Structured rate-limit event logging in traces

### MCP

- **MCP-V2-01**: Bidirectional MCP — expose existing tools as an MCP server for other clients
- **MCP-V2-02**: Connection to a real public HTTP/SSE MCP server
- **MCP-V2-03**: MCP server health shown in the observability dashboard

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| User authentication / accounts | Anonymous session id is sufficient; auth adds surface with no portfolio benefit (foundation stays auth-upgradable) |
| Multi-agent orchestration | Low signal-to-effort for a portfolio; easy to do poorly; explicitly deferred |
| Per-memory editing UI | High UI cost, low recruiter legibility; "clear all" + read-only list suffices |
| Memory importance scoring / auto-forgetting / summarization | Hard to demo correctly; burns quota; recency + cap is enough |
| Paid models / paid providers | $0 budget; free-tier operation is the core differentiator |
| OCR for scanned PDFs | High complexity; accept text-layer PDFs only |
| Web URL / corpus ingestion (scraping) | Scope creep; session-scoped file upload only |
| Reranking (cross-encoder) | Marginal demo benefit; good chunking + pgvector is sufficient |
| OpenTelemetry / external APM (Sentry, Datadog) / alerting | Complex/paid; custom Supabase traces deliver more legibly here |
| Self-hosted Langfuse | Requires Docker; incompatible with Vercel serverless |
| stdio MCP transport | Impossible on Vercel serverless; HTTP/Streamable only |
| MCP resource/prompt primitives; reimplementing MCP from scratch | High complexity, low legibility; use the official SDK, tools only |

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| FOUND-05 | Phase 1 | Pending |
| MEM-01 | Phase 2 | Pending |
| MEM-02 | Phase 2 | Pending |
| MEM-03 | Phase 2 | Pending |
| MEM-04 | Phase 2 | Pending |
| MEM-05 | Phase 2 | Pending |
| MEM-06 | Phase 2 | Pending |
| MEM-07 | Phase 2 | Pending |
| RAG-01 | Phase 3 | Pending |
| RAG-02 | Phase 3 | Pending |
| RAG-03 | Phase 3 | Pending |
| RAG-04 | Phase 3 | Pending |
| RAG-05 | Phase 3 | Pending |
| RAG-06 | Phase 3 | Pending |
| RAG-07 | Phase 3 | Pending |
| RAG-08 | Phase 3 | Pending |
| RAG-09 | Phase 3 | Pending |
| OBS-01 | Phase 4 | Pending |
| OBS-02 | Phase 4 | Pending |
| OBS-03 | Phase 4 | Pending |
| OBS-04 | Phase 4 | Pending |
| OBS-05 | Phase 4 | Pending |
| OBS-06 | Phase 4 | Pending |
| MCP-01 | Phase 5 | Pending |
| MCP-02 | Phase 5 | Pending |
| MCP-03 | Phase 5 | Pending |
| MCP-04 | Phase 5 | Pending |
| MCP-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32 ✓
- Unmapped: 0 ✓

Note: The file previously stated 31 total; a recount yields 32 (FOUND×5, MEM×7, RAG×9, OBS×6, MCP×5). All are mapped.

---
*Requirements defined: 2026-06-28*
*Last updated: 2026-06-28 after roadmap creation — traceability populated*
