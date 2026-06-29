# Architecture Research

**Domain:** Serverless ReAct Agent — Memory + RAG + MCP + Observability Integration
**Researched:** 2026-06-28
**Confidence:** MEDIUM (cross-checked web sources; no paid docs access)

---

## Context

This document answers the integration question: **how should the new components fit into the existing architecture without breaking it?** The existing system is a 2-node LangGraph StateGraph (agent_node ↔ tool_node), deployed on Vercel serverless via FastAPI. All four new pillars (persistence, memory, RAG, MCP, observability) must integrate without requiring a long-lived process, a writable local filesystem, or auth.

Read `.planning/codebase/ARCHITECTURE.md` before this document — it is the ground truth for the current system. This file only describes the **delta**.

---

## Extended System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Browser (React + Vite)                                                             │
│                                                                                     │
│  ┌──────────────┐  ┌────────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │  ChatPanel   │  │  ReasoningPanel    │  │  TracesDashboard │  │  DocUpload    │ │
│  │  +MemoryBadge│  │  +ContextChunks    │  │  (NEW)           │  │  Panel (NEW)  │ │
│  └──────┬───────┘  └────────────────────┘  └──────────────────┘  └───────┬───────┘ │
│         │ X-Session-Id header (localStorage UUID)                         │         │
└─────────┼───────────────────────────────────────────────────────────────-─┼─────────┘
          │ (A) POST /api/run + history                                      │ (B) POST /api/documents/upload
          │     X-Session-Id: <uuid>                                         │
          ▼                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FastAPI (backend/api.py + api/index.py)                                            │
│                                                                                     │
│  Existing routes: /run /config /suggestions /evals /trace                          │
│  New routes:      /api/documents/upload  /api/documents                             │
│                   /api/traces (paginated, replaces in-memory RUNS)                  │
│                   /api/health/ping  (keep-alive probe)                              │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  LangGraph StateGraph  (backend/agent/graph.py)                              │   │
│  │                                                                               │   │
│  │  PRE-GRAPH (new, in api.py before build_graph):                              │   │
│  │    1. Read thread memory from PostgresStore (long-term context)              │   │
│  │    2. Inject into SYSTEM_PROMPT as "What I know about you:" block            │   │
│  │                                                                               │   │
│  │  ┌─────────────────┐  ←──────────────  ┌─────────────────────────┐          │   │
│  │  │  agent_node     │                   │  should_continue        │          │   │
│  │  │  (LLM call)     │  ──────────────►  │  (MAX_ITERATIONS=10)   │          │   │
│  │  │  tool schemas:  │                   └─────────────────────────┘          │   │
│  │  │   web_search    │                             │                          │   │
│  │  │   python_exec   │                             │ tool calls               │   │
│  │  │   calculator    │                             ▼                          │   │
│  │  │   retrieve_ctx  │◄──────────────  ┌─────────────────────────┐           │   │
│  │  │   [mcp_tools]*  │                 │  tool_node              │           │   │
│  │  └─────────────────┘                 │  (execute tools)        │           │   │
│  │                                      │  +create Step           │           │   │
│  │  POST-GRAPH (new, in api.py):         └─────────────────────────┘           │   │
│  │    3. Extract salient facts → write to PostgresStore (long-term)            │   │
│  │    4. Persist AgentResponse → traces table (observability)                  │   │
│  │                                                                               │   │
│  │  Checkpointer: PostgresSaver (replaces in-memory for short-term memory)     │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
          │                                          │
          │ SQL (Transaction Pooler port 6543)       │ Gemini Embedding API
          ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Supabase (Postgres + pgvector)                                                     │
│                                                                                     │
│  langgraph_checkpoints  ← managed by PostgresSaver.setup()                         │
│  langgraph_store        ← managed by PostgresStore (cross-thread memory)           │
│  documents              ← upload metadata                                           │
│  document_chunks        ← RAG retrieval units, vector(768)                         │
│  traces                 ← persisted AgentResponse (run_id, steps, usage, token)   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | File | Communicates With |
|-----------|---------------|------|-------------------|
| `supabase_client` (new) | Shared Supabase async client, pooler connection string | `backend/agent/db.py` | All new backend modules |
| `PostgresSaver` | Short-term message checkpoint per thread_id | `langgraph-checkpoint-postgres` (PyPI) | `build_graph()` in `graph.py` |
| `PostgresStore` | Long-term cross-thread memory (facts, preferences) | `langgraph` store module | `api.py` pre/post-graph hooks |
| `memory.py` (new) | Read/write long-term facts; format memory block for system prompt | `backend/agent/memory.py` | `api.py`, `PostgresStore` |
| `documents.py` (new) | Upload endpoint handler, text extraction, chunking, embedding, pgvector insert | `backend/agent/documents.py` | Gemini embed API, `db.py` |
| `retrieve_context` tool (new) | RAG retrieval as a LangGraph-native tool | `backend/agent/tools.py` (add here) | pgvector via `db.py` |
| `mcp_adapter.py` (new) | MultiServerMCPClient init; adapt MCP tools to LangChain tool format | `backend/agent/mcp_adapter.py` | External MCP servers (HTTP/SSE) |
| `TracesDashboard` (new, frontend) | Persisted runs view with step timeline, token/cost chart | `frontend/src/components/TracesDashboard.tsx` | `GET /api/traces` |
| `DocUploadPanel` (new, frontend) | File upload UI, status feedback, doc list | `frontend/src/components/DocUploadPanel.tsx` | `POST /api/documents/upload` |

---

## Supabase Schema

### Migration approach

Run these as Supabase migrations (SQL files under `supabase/migrations/`). LangGraph's `PostgresSaver.setup()` creates its own tables automatically; do not replicate those. Only define the application-specific tables below.

```sql
-- Enable pgvector extension (one-time)
create extension if not exists vector;

-- ============================================================
-- PILLAR 1: RAG — document metadata + chunk embeddings
-- ============================================================

create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  session_id  text not null,          -- maps to frontend localStorage UUID
  filename    text not null,
  mime_type   text,
  byte_size   int,
  created_at  timestamptz default now()
);

create index on documents (session_id);

create table if not exists document_chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  session_id  text not null,          -- denormalized for fast filtered search
  chunk_index int not null,
  content     text not null,
  embedding   vector(768),            -- Gemini text-embedding-004 output dims
  token_count int,
  created_at  timestamptz default now()
);

create index on document_chunks (session_id);
-- HNSW index for cosine similarity (better recall than IVFFlat at this scale)
create index on document_chunks using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- ============================================================
-- PILLAR 2: Observability — persisted run traces
-- ============================================================

create table if not exists traces (
  run_id      text primary key,
  thread_id   text,                   -- same as session_id when memory is on
  query       text not null,
  steps       jsonb not null,         -- serialized list[Step] from AgentState
  final_answer text,
  status      text,                   -- 'success' | 'error' | 'max_iterations'
  usage       jsonb,                  -- UsageTracker snapshot: tokens, cost, provider
  elapsed_ms  int,
  created_at  timestamptz default now()
);

create index on traces (thread_id);
create index on traces (created_at desc);

-- ============================================================
-- PILLAR 2: Keep-alive — ping table (prevents 7-day pause)
-- ============================================================

create table if not exists keepalive (
  id    int primary key default 1,
  pinged_at timestamptz default now()
);

insert into keepalive (id, pinged_at) values (1, now())
  on conflict (id) do nothing;
```

**Notes on what PostgresSaver creates automatically (do not define these):**
- `checkpoints` — LangGraph checkpoint blobs per thread_id
- `checkpoint_writes` — write-ahead log for checkpoints
- `checkpoint_migrations` — internal schema version tracking

These are created by calling `PostgresSaver.setup()` once at app startup (idempotent).

---

## Integration Points with Existing Code

### 1. Connection Layer — `backend/agent/db.py` (new file)

Single module that owns the Supabase connection. All other new modules import from here.

```python
# backend/agent/db.py
import os
from supabase import create_client, Client
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Supabase client (for documents, traces, keepalive)
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Transaction Pooler URI — port 6543, NOT 5432 (critical for serverless)
# Disable prepared statements: pool_mode=transaction does not support them
POOLER_URI = os.environ["SUPABASE_POOLER_URI"]  # postgres://...@pooler.supabase.com:6543/postgres?pgbouncer=true

def get_checkpointer() -> PostgresSaver:
    return PostgresSaver.from_conn_string(POOLER_URI)

def get_store() -> PostgresStore:
    return PostgresStore.from_conn_string(POOLER_URI)
```

**Why Transaction Pooler (port 6543) not direct (port 5432):**
Vercel serverless functions spawn fresh processes per request. Direct Postgres connections accumulate and are never cleanly closed. Supabase's Transaction Pooler (Supavisor) multiplexes many short-lived connections onto a small pool. At free-tier scale, direct connections will exhaust the pool under minimal load.

**One-time setup call in `backend/api.py` startup:**
```python
# In api.py lifespan or at module level (runs once per cold start)
with get_checkpointer() as cp:
    cp.setup()  # creates LangGraph checkpoint tables if not exist (idempotent)
```

---

### 2. Memory — Thread ID Flow and Injection Points

**Frontend → Backend thread ID propagation:**

The frontend already generates a `sessionId` UUID in `useAgent.ts` and persists it in localStorage. Extend the existing `sendQuery()` call to send it:

```typescript
// frontend/src/hooks/useAgent.ts — add to the fetch headers
headers: {
  "Content-Type": "application/json",
  "X-Session-Id": sessionId,  // already exists in localStorage state
}
```

In `backend/api.py`, extract and thread through:

```python
# backend/api.py — in run_agent()
thread_id = request.headers.get("X-Session-Id", f"anon-{run_id}")
config = {"configurable": {"thread_id": thread_id}}
```

**Short-term memory (PostgresSaver — message history across turns):**

Modify `build_graph()` in `backend/agent/graph.py` to accept an optional checkpointer:

```python
# backend/agent/graph.py
def build_graph(checkpointer=None):
    ...
    return graph.compile(checkpointer=checkpointer)
```

In `backend/api.py`, pass the checkpointer when building the graph:

```python
# backend/api.py — in _stream_agent()
with get_checkpointer() as checkpointer:
    graph = build_graph(checkpointer=checkpointer)
    async for state in graph.astream(initial_state, config=config):
        ...
```

With this, LangGraph reads the last checkpoint for `thread_id` before running `agent_node`, and writes a new checkpoint after each node completes. The existing history-from-frontend mechanism (last 8 messages) becomes redundant for repeat sessions — the checkpointer restores the full conversation from Supabase.

**Long-term memory (PostgresStore — facts across different sessions):**

Read before the graph, write after. Lives in `backend/agent/memory.py`:

```python
# backend/agent/memory.py
from langgraph.store.postgres import PostgresStore

MEMORY_NAMESPACE = ("memory", "{thread_id}")  # LangGraph namespace pattern

def load_memory_block(store: PostgresStore, thread_id: str) -> str:
    """Return formatted string to inject into SYSTEM_PROMPT."""
    items = store.search(("memory", thread_id), limit=10)
    if not items:
        return ""
    facts = "\n".join(f"- {item.value['fact']}" for item in items)
    return f"\n\nWhat I know about you:\n{facts}"

def save_memory_facts(store: PostgresStore, thread_id: str, facts: list[str]):
    """Extract and persist salient facts after a turn completes."""
    for i, fact in enumerate(facts):
        store.put(("memory", thread_id), f"fact-{i}", {"fact": fact})
```

In `backend/api.py`, wrap the graph call:

```python
# Before graph.astream():
with get_store() as store:
    memory_block = load_memory_block(store, thread_id)
    # Append to system prompt: pass memory_block into build_graph() or via initial_state
    
# After _stream_agent() yields final answer:
    facts = extract_facts_with_llm(final_answer, query)  # optional LLM call
    save_memory_facts(store, thread_id, facts)
```

**Memory injection point:** The memory block is injected into the `SystemMessage` inside `agent_node()` in `backend/agent/graph.py`. Currently `agent_node` constructs its own `SystemMessage` with `SYSTEM_PROMPT`. Pass `memory_block` as an additional parameter via the `AgentState` or as a field on the initial state.

---

### 3. RAG — Ingestion and Retrieval

**Ingestion pipeline** lives in `backend/agent/documents.py` (new file):

```
POST /api/documents/upload
  ↓
Extract text (PyMuPDF for PDF, plain text for .txt)
  ↓
Recursive character splitter: 512 tokens, 50-token overlap
  ↓
Gemini text-embedding-004: embed each chunk (768-dim vector)
  - Batch in groups of 5 (conservative; free tier)
  - tenacity retry with exponential backoff on 429
  ↓
Supabase: INSERT into documents + document_chunks
  ↓
Return 200 with {document_id, chunk_count}
```

**Serverless timeout constraint:** Vercel Hobby plan serverless functions have a 10-second execution limit. A 10-page PDF with 30 chunks requires ~6 Gemini embedding calls (5 chunks/batch). At ~200ms per batch, that is ~1.2s for embedding alone — manageable within 10s if text extraction is fast. Hard limit: reject files larger than 2MB or 30 chunks at the upload endpoint.

**Retrieval tool** added to `backend/agent/tools.py`:

```python
# backend/agent/tools.py — add retrieve_context
async def retrieve_context(query: str, session_id: str, top_k: int = 4) -> str:
    """Search pgvector for chunks relevant to query, scoped to session_id."""
    query_embedding = embed_text(query)  # Gemini text-embedding-004
    supabase = get_supabase()
    # RPC call to a Supabase stored procedure for vector search
    result = supabase.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "session_id": session_id,
        "match_count": top_k,
    }).execute()
    chunks = result.data
    if not chunks:
        return "No relevant document context found for this session."
    return "\n\n".join(f"[Chunk {c['chunk_index']}]: {c['content']}" for c in chunks)
```

Add this to `TOOLS` dict and `TOOL_SCHEMAS` in `backend/agent/graph.py`.

The `session_id` is passed via the `AgentState` (add a `session_id: str` field to `backend/agent/state.py`).

**Supabase stored procedure** (add to a migration):
```sql
create or replace function match_chunks(
  query_embedding vector(768),
  session_id text,
  match_count int default 4
)
returns table (chunk_index int, content text, similarity float)
language sql stable as $$
  select chunk_index, content,
         1 - (embedding <=> query_embedding) as similarity
  from document_chunks
  where document_chunks.session_id = match_chunks.session_id
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

---

### 4. MCP — Client Integration Under Serverless

**Approach:** The agent acts as an MCP **host** (client) that calls external MCP **servers** via HTTP/SSE or Streamable HTTP transport. The agent does not expose itself as an MCP server in this milestone (that can be Phase 5/future).

**Library:** `langchain-mcp-adapters` (PyPI) — converts MCP tool descriptors into LangChain-compatible tools that slot into the existing `TOOL_SCHEMAS` + `TOOLS` pattern.

**Serverless constraint:** MCP HTTP/SSE sessions are per-invocation (stateless). The `MultiServerMCPClient` creates a fresh session per request and closes it when done. This is the correct pattern under serverless — no persistent background process.

**Integration file** `backend/agent/mcp_adapter.py` (new):

```python
# backend/agent/mcp_adapter.py
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVERS = {
    # Example: a public MCP server, or a separately deployed FastMCP server
    "fetch": {
        "url": os.environ.get("MCP_FETCH_SERVER_URL", ""),
        "transport": "streamable_http",  # 2025-03-26 spec
    },
}

async def get_mcp_tools():
    """Fetch MCP tool descriptors and convert to LangChain tools."""
    if not any(v.get("url") for v in MCP_SERVERS.values()):
        return []  # MCP disabled if no server URL configured
    async with MultiServerMCPClient(MCP_SERVERS) as client:
        tools = await client.get_tools()
    return tools  # list of LangChain BaseTool objects
```

In `build_graph()`, MCP tools are merged with native tools:

```python
# backend/agent/graph.py — build_graph()
async def build_graph(mcp_tools: list = None, checkpointer=None):
    all_tools = list(TOOLS.values()) + (mcp_tools or [])
    tool_node = ToolNode(all_tools)
    ...
```

**Transport note:** Use `streamable_http` (2025-03-26 MCP spec) rather than the legacy `sse` transport (2024-11-05 spec). The legacy SSE transport requires a persistent connection, which is incompatible with serverless. Streamable HTTP is stateless HTTP with optional SSE for streaming responses.

---

### 5. Observability — Trace Persistence and Dashboard

**What already exists:** `UsageTracker` in `backend/agent/llms.py` captures tokens, estimated cost, provider, latency per call. `RUNS` dict in `backend/api.py` stores last 100 `AgentResponse` objects in-memory.

**Extension:** After the SSE stream completes in `_stream_agent()`, fire-and-forget async insert to the `traces` table:

```python
# backend/api.py — after final SSE event is emitted
asyncio.create_task(persist_trace(run_id, thread_id, query, response))
```

```python
# backend/agent/db.py or api.py
async def persist_trace(run_id, thread_id, query, response: AgentResponse):
    supabase = get_supabase()
    supabase.table("traces").insert({
        "run_id": run_id,
        "thread_id": thread_id,
        "query": query,
        "steps": [step.__dict__ for step in response.steps],
        "final_answer": response.result,
        "status": response.status,
        "usage": response.usage.__dict__ if response.usage else None,
        "elapsed_ms": response.elapsed_ms,
    }).execute()
```

**New endpoint:** `GET /api/traces?limit=20&offset=0` — reads from Supabase, replaces the current in-memory trace endpoint. Keep the existing `GET /api/trace/{run_id}` for backwards compatibility but make it also fall back to Supabase if not in memory.

**Frontend dashboard** (`TracesDashboard.tsx`): a new tab or panel on the About page that calls `GET /api/traces` and renders:
- Timeline of recent runs (run_id, timestamp, elapsed_ms, status)
- Token usage / estimated cost bar chart per run
- Step count per run
- Expandable detail for each run's step trace

---

## Data Flow Summary

### Chat Request with Memory + RAG

```
Browser → POST /api/run (X-Session-Id: <uuid>)
  │
  ├── api.py extracts thread_id = X-Session-Id header
  ├── get_checkpointer() → PostgresSaver opens connection
  ├── get_store() → PostgresStore opens connection
  ├── load_memory_block(store, thread_id) → injects into system prompt
  ├── build_graph(checkpointer) + mcp_tools (if configured)
  │
  ├── graph.astream(initial_state, config={"configurable": {"thread_id": thread_id}})
  │     │
  │     ├── agent_node: LLM sees system prompt + memory block + message history
  │     │   may call retrieve_context(query, session_id)
  │     │   may call web_search / python_executor / calculator / mcp_tool
  │     │
  │     └── tool_node: executes tools, creates Steps, emits SSE
  │
  ├── SSE stream emits thought/action/observation/final events → browser
  ├── save_memory_facts(store, thread_id, extracted_facts)  [post-graph]
  └── persist_trace(run_id, thread_id, ...)                 [fire-and-forget]
```

### Document Upload

```
Browser → POST /api/documents/upload (X-Session-Id: <uuid>, file: multipart)
  │
  ├── Extract text (PyMuPDF / plain text parser)
  ├── Split into chunks (512 tokens, 50-token overlap)
  ├── Batch embed via Gemini text-embedding-004 (5 chunks/batch, tenacity retry)
  ├── INSERT document + document_chunks into Supabase
  └── Return {document_id, chunk_count, filename}
```

### Keep-Alive (Vercel Cron)

```
Vercel Cron (every 5 days) → GET /api/health/ping
  │
  └── api.py: UPDATE keepalive SET pinged_at = now() WHERE id = 1
```

---

## Build Order and Dependencies

The pillars are sequentially dependent. Each pillar requires the previous one to be in place before implementation begins.

```
PHASE 1: Foundation (prerequisite for all pillars)
  - Supabase project created, pgvector enabled
  - Schema migration (documents, document_chunks, traces, keepalive tables)
  - backend/agent/db.py: connection module (pooler URI, get_supabase, get_checkpointer, get_store)
  - PostgresSaver.setup() wired into api.py startup
  - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_POOLER_URI added to .env + Vercel env
  - Vercel Cron keep-alive route (/api/health/ping) + vercel.json cron config
  DEPENDENCY: None

PHASE 2: Memory (short-term + long-term)
  - frontend/src/hooks/useAgent.ts: send X-Session-Id header
  - backend/api.py: extract thread_id from header, pass config to graph
  - backend/agent/graph.py: build_graph(checkpointer) — compile with PostgresSaver
  - backend/agent/memory.py: load_memory_block, save_memory_facts
  - backend/agent/state.py: add session_id field to AgentState
  DEPENDENCY: Phase 1 (connection layer, PostgresSaver tables)

PHASE 3: RAG
  - backend/agent/documents.py: upload handler, text extraction, chunking, embedding, pgvector insert
  - backend/api.py: POST /api/documents/upload + GET /api/documents routes
  - backend/agent/tools.py: retrieve_context tool
  - backend/agent/graph.py: add retrieve_context to TOOLS + TOOL_SCHEMAS
  - Supabase: match_chunks() stored procedure migration
  - frontend: DocUploadPanel component
  DEPENDENCY: Phase 1 (document_chunks table, Supabase client), Phase 2 (session_id in AgentState)

PHASE 4: Observability
  - backend/api.py: persist_trace() async fire-and-forget after SSE stream
  - backend/api.py: GET /api/traces endpoint (reads from Supabase)
  - frontend: TracesDashboard component
  DEPENDENCY: Phase 1 (traces table), Phase 2 (thread_id available)

PHASE 5: MCP
  - backend/agent/mcp_adapter.py: MultiServerMCPClient with HTTP transport
  - backend/agent/graph.py: merge mcp_tools into graph at build time
  - MCP server URL(s) configured via env vars (can be empty = feature disabled)
  DEPENDENCY: Phase 1 (db.py structure), Phase 2 (graph architecture stable)
```

**Why this order:**
- Foundation must be first because the Supabase client is imported by every subsequent module.
- Memory before RAG because RAG uses session_id from AgentState, which is added in Phase 2.
- Observability before MCP because observability is purely additive (persistence), while MCP modifies the graph build path and requires the architecture to be stable first.
- MCP last because it is the most isolated (can be toggled by env var) and adds no dependencies for earlier phases.

---

## Architectural Patterns

### Pattern 1: Context Manager per Request (not singleton)

**What:** Each serverless request opens its own Supabase/PostgresSaver connection via Python context manager (`with get_checkpointer() as cp:`) and closes it at request end.

**Why:** Serverless functions are ephemeral; a module-level singleton connection leaks between cold starts and becomes stale. Context managers ensure connections are opened fresh and closed cleanly on each invocation.

**Trade-off:** ~20ms connection overhead per request. Acceptable at portfolio scale; a connection pool cache (e.g., using `asyncpg` pool with a short lifetime) can reduce this if it becomes a latency issue.

---

### Pattern 2: Session ID as Namespace Key (not user auth)

**What:** Anonymous `sessionId` UUID (generated client-side, stored in localStorage) flows through as `thread_id` to scope checkpoints, memory facts, and document chunks.

**Why:** No auth means no secure server-side session concept. The UUID is good enough for demo isolation. Documents and memory are scoped to `session_id` so one browser session cannot read another's data.

**Trade-off:** Anyone with a session_id UUID can read that session's memory. For a portfolio demo, this is acceptable. The schema is designed so adding auth later is a matter of replacing the UUID with a user_id foreign key in the relevant tables.

---

### Pattern 3: RAG as a Native Tool (not pipeline pre-step)

**What:** `retrieve_context` is registered as a fourth tool in the `TOOLS` dict, not invoked automatically before every request.

**Why:** Preserves the existing tool-selection ethos — the LLM decides when to retrieve. Forcing RAG retrieval on every query would degrade performance on queries where documents are irrelevant (math, code, web lookups). The LLM is instructed in `TOOL_SCHEMAS` to call `retrieve_context` "when the user's question may be answered by documents they have uploaded."

**Trade-off:** If the LLM does not call `retrieve_context` when it should, RAG fails silently. The web search guardrail pattern (forcing web_search for current-fact queries) could be extended to force `retrieve_context` when documents are detected in the session — but this is a tuning decision, not an architecture one.

---

### Pattern 4: Fire-and-Forget for Trace Persistence

**What:** `asyncio.create_task(persist_trace(...))` is called after the final SSE event. The HTTP response stream is already closed; the task runs independently.

**Why:** Trace persistence is non-critical path. Blocking the SSE stream on a Supabase insert would add latency to every response.

**Trade-off:** If the serverless function terminates before the task completes, the trace is lost. On Vercel, function execution continues briefly after the response is sent, so this is acceptable for most cases. Add a fallback: keep the in-memory RUNS dict as a write-through cache so GET /api/trace/{run_id} always works for the most recent runs.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Postgres Connection from Serverless

**What people do:** Use the direct Postgres URI (port 5432) from Vercel functions because it is simpler.

**Why it's wrong:** Each serverless invocation creates a new connection. Under any load, Supabase's free tier (max 60 direct connections) is exhausted within seconds.

**Do this instead:** Use the Transaction Pooler URI (port 6543) from Supabase project settings. Disable prepared statements (`pgbouncer=true` query param for asyncpg, `prepare_threshold=None` for psycopg3).

---

### Anti-Pattern 2: Embedding Every Chunk on Every Query

**What people do:** Re-embed query text using Gemini on every agent turn to perform RAG retrieval.

**Why it's wrong:** Gemini free tier is rate-limited. Embedding on every turn means a 10-turn conversation does 10 embedding calls even when no document question is asked.

**Do this instead:** Only embed and retrieve when the `retrieve_context` tool is called by the LLM. The model decides when RAG is needed, not the pipeline.

---

### Anti-Pattern 3: Storing Full Message History in Long-Term Memory

**What people do:** Write the entire conversation to the long-term memory store after each turn.

**Why it's wrong:** The `langgraph_checkpoints` table already stores full message history per thread. Duplicating it in the long-term store (PostgresStore) wastes storage and causes context explosion — the system prompt grows unboundedly.

**Do this instead:** Extract only salient facts from the final answer (e.g., "user prefers Python", "user's name is X") and store those as discrete key-value items in PostgresStore. Keep fact extraction lightweight — a one-shot LLM call with a small prompt like "List 0-3 facts about the user from this conversation. Reply with a JSON array."

---

### Anti-Pattern 4: MCP stdio Transport on Serverless

**What people do:** Configure MCP servers with stdio transport (default in many examples) because it is simpler to set up locally.

**Why it's wrong:** stdio transport requires a long-lived child process. Vercel serverless has no persistent process — the function dies after the response.

**Do this instead:** Only use HTTP-based MCP transport (`streamable_http` or legacy `sse`) for any MCP servers consumed by the agent. Configure MCP server URLs via environment variables; if the URL is empty, skip MCP tool loading entirely. This makes MCP a gracefully degradable feature.

---

## Scalability Considerations (Portfolio Scale)

This is a portfolio project. The architecture is designed for correctness and demo reliability, not horizontal scale.

| Concern | At demo scale (1-5 concurrent) | If traffic spikes |
|---------|-------------------------------|-------------------|
| Supabase connections | Transaction Pooler handles easily | Pooler has a 15-connection limit on free tier — upgrade or add connection reuse |
| Embedding rate limits | Fine; sequential batching | Implement queue-based ingestion (Supabase Edge Function + queue table) |
| Checkpoint table size | Negligible | Add retention policy (delete checkpoints older than 30 days) |
| Trace table growth | ~1KB/run; 1000 runs = 1MB | Add pagination, archive old traces |
| MCP latency | One round trip to external server per tool call | Pre-warm tool schema cache at startup |

---

## Sources

- [Supabase Connection Docs: Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres) — Transaction Pooler (MEDIUM confidence)
- [Supabase Supavisor FAQ](https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI) — pooler mode details (MEDIUM confidence)
- [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — PostgresSaver + thread_id config (MEDIUM confidence)
- [LangGraph Memory Guide](https://focused.io/lab/persistent-agent-memory-in-langgraph) — cross-thread store patterns (MEDIUM confidence)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters) — MultiServerMCPClient API (MEDIUM confidence)
- [MCP Transports Spec](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) — Streamable HTTP vs SSE (MEDIUM confidence)
- [MCP Transport Future](https://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/) — serverless SSE deprecation direction (MEDIUM confidence)
- [Vercel MCP Server Support](https://vercel.com/changelog/mcp-server-support-on-vercel) — Vercel MCP compatibility (MEDIUM confidence)
- [Gemini Embedding Docs](https://ai.google.dev/gemini-api/docs/embeddings) — text-embedding-004, 768 dims (MEDIUM confidence)
- [Gemini Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits) — free tier limits (MEDIUM confidence)
- [pgvector RAG Schema](https://codeawake.com/blog/postgresql-vector-database) — table structure patterns (MEDIUM confidence)
- [Supabase Free Tier Pause](https://github.com/travisvn/supabase-pause-prevention) — 7-day inactivity policy, keep-alive patterns (MEDIUM confidence)

---

*Architecture research for: ReAct Agent — Memory + RAG + MCP + Observability integration*
*Researched: 2026-06-28*
