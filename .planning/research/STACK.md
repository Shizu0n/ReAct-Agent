# Technology Stack — New Pillars

**Project:** ReAct Agent (Milestone 2: Memory + RAG + MCP + Observability)
**Researched:** 2026-06-29
**Scope:** Additive only — do NOT re-research the existing stack. This document covers what to ADD.

---

## Existing Stack (Do Not Change)

Defined in `.planning/codebase/STACK.md`. Key constraints for this milestone:

- Python 3.11 / FastAPI 0.115.4 / LangGraph 0.2.45 / LangChain 0.3.7
- Vercel Hobby (serverless, ephemeral FS, 1 cron job, 300s timeout, 2 GB / 1 vCPU)
- Multi-provider LLM: Gemini → Groq → GitHub Models (free only, zero spend)

**LangGraph version note (CRITICAL):** `langgraph 0.2.45` is likely incompatible with `langgraph-checkpoint-postgres 3.1.0` (released May 2026). The first implementation task must resolve the version upgrade path before writing persistence code. Pin LangGraph to the minimum version that satisfies checkpoint-postgres 3.1.0 and verify no breaking changes in the graph API.

---

## Platform Constraints

| Constraint | Value | Source |
|------------|-------|--------|
| Supabase free DB | 500 MB, pgvector included | Supabase pricing 2026 |
| Supabase inactivity pause | 7 days → project paused | Supabase free tier policy |
| Supabase pooler URL | port 6543 (Supavisor transaction mode) | Supabase docs |
| Supabase direct URL | port 5432 — migrations only, NOT serverless | Supabase docs |
| Vercel function timeout | 300 s max (Hobby) | Vercel docs |
| Vercel memory | 2 GB / 1 vCPU, fixed (not configurable on Hobby) | Vercel docs |
| Vercel cron jobs | 1 per project on Hobby plan | Vercel docs |
| Gemini embedding free | gemini-embedding-001, ~100 RPM / ~1000 RPD | Gemini API pricing (approx, project-level) |
| MCP SSE transport | DEPRECATED Dec 2025 — do not use | MCP blog Dec 2025 |

---

## Pillar 1 — Persistence Backbone (Supabase + psycopg)

### Why Supabase

Supabase is the only free-tier Postgres provider that ships pgvector on the free plan, has a Python ecosystem, and can unify memory checkpoints, vector store, and trace storage in a single database. The free tier (500 MB, pgvector included) is sufficient for a portfolio demo. The 7-day inactivity pause is the main operational risk; it is mitigated by a keep-alive cron job (see Pillar 5).

### Connection Library

Use **psycopg 3** (package name: `psycopg`, with `psycopg[binary]` for binary wheels). Do NOT use asyncpg.

**Why psycopg3 over asyncpg:** Supabase's Supavisor uses PgBouncer transaction mode on port 6543. asyncpg relies on prepared statements that break in transaction mode. psycopg3 has a `prepare_threshold=None` option that disables prepared statements cleanly.

```python
# Serverless connection pattern — always use pooler URL
import psycopg
conn = await psycopg.AsyncConnection.connect(
    SUPABASE_POOLER_URL,  # port 6543, not 5432
    prepare_threshold=None,  # required for transaction-mode pooler
    autocommit=True,
)
```

Connection strings:
- Pooler (transactions, serverless): `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`
- Direct (migrations, schema changes only): `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`

| Library | Version | Purpose |
|---------|---------|---------|
| `psycopg[binary]` | `>=3.2` | Async Postgres driver for memory + trace persistence |
| `psycopg-pool` | `>=3.2` | Optional connection pool (avoid creating new connections per request) |

**Confidence: MEDIUM** (psycopg3 + Supabase compatibility confirmed by community; version pinning unverified against CI)

---

## Pillar 2 — Long-Term Memory

### Architecture Decision

LangGraph provides two complementary persistence layers. Use both:

1. **AsyncPostgresSaver** (checkpointer) — thread-scoped conversation continuity. Persists the full LangGraph state (messages, steps, iteration count) keyed by `thread_id`. This is "short-term" memory within a conversation thread — it lets the agent resume where it left off if a session reconnects.

2. **PostgresStore** — cross-thread long-term memory. Stores structured facts the agent has learned about a user (preferences, named entities mentioned). Keyed by a custom namespace (e.g., `("user", session_id)`).

For this project, `thread_id = anonymous_session_id` (generated on first visit, stored in localStorage). No auth required.

### Package

| Library | Version | Purpose |
|---------|---------|---------|
| `langgraph-checkpoint-postgres` | `>=3.1.0` | AsyncPostgresSaver + PostgresStore |

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# One-time setup (call at app startup or in a migration script):
async with AsyncPostgresSaver.from_conn_string(SUPABASE_POOLER_URL) as checkpointer:
    await checkpointer.setup()  # creates checkpoint tables

# Compile graph with checkpointer:
graph = builder.compile(checkpointer=checkpointer)

# Invoke with thread_id:
config = {"configurable": {"thread_id": session_id}}
result = await graph.ainvoke(state, config=config)
```

**What NOT to use:**

- `MemorySaver` (LangGraph's in-memory checkpointer): lost on cold start — this is the exact problem we're solving.
- `SqliteSaver`: no concurrent access, no serverless support, no vector search.

**Confidence: MEDIUM** (pattern confirmed via LangChain docs and community posts; exact version compatibility with existing LangGraph 0.2.45 unverified — flag as implementation risk)

---

## Pillar 3 — RAG over User-Uploaded Documents

RAG has three sub-problems: document parsing, chunking, and retrieval. Each needs a specific library choice.

### 3a. Document Parsing

**Recommended: `pymupdf4llm`** (part of the PyMuPDF family)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `pymupdf4llm` | `>=0.0.17` | PDF → Markdown extraction for LLM use | Fastest (0.12s/doc), outputs clean Markdown, preserves structure, LangChain-native integration |

**Why not `unstructured`:** Heavy dependencies (LibreOffice, tesseract optional), 1.3s/doc, overkill for a portfolio demo. Installation on Vercel serverless is problematic.

**Why not bare `pypdf`:** Spacing artifacts, no table/structure awareness. Adequate but pymupdf4llm is strictly better for RAG quality.

For DOCX: `python-docx` (lightweight, no heavy dependencies). For plain text: no parsing needed.

```python
import pymupdf4llm
md_text = pymupdf4llm.to_markdown("document.pdf")
```

### 3b. Text Chunking

**Recommended: LangChain `RecursiveCharacterTextSplitter`** (already available via `langchain-text-splitters`)

This is the standard choice. No new package needed — it is part of the existing `langchain-core` dependency.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,   # characters; tune based on embedding token limits
    chunk_overlap=100,
    separators=["\n\n", "\n", " ", ""],
)
chunks = splitter.split_text(md_text)
```

**Why not semantic chunking:** Requires an LLM call per chunk boundary — burns free quota and adds latency. Recursive character splitting at 800 chars is fast, free, and good enough for most RAG quality levels.

### 3c. Embeddings

**Recommended: Gemini `gemini-embedding-001` via `langchain-google-genai`**

| Library | Version | Model | Dimensions | Cost |
|---------|---------|-------|------------|------|
| `langchain-google-genai` | `>=2.0` | `gemini-embedding-001` | 768 (truncated from 3072) | Free |

**Model details:**
- Model ID: `gemini-embedding-001` (text-only; uses the Gemini API key you already have)
- Default output: 3072 dimensions. Set `output_dimensionality=768` to reduce storage (MRL truncation preserves quality).
- Free tier rate limits: approximately 100 RPM, 1,000 RPD (project-level; verify actual limits in Google AI Studio — they vary by account age and region).
- Alternative: `gemini-embedding-2` (multimodal, also free, but multimodal support is unnecessary for text-only RAG; stick to `gemini-embedding-001`).

**Critical: batch and rate-limit handling.** At 100 RPM, ingesting a 100-chunk document takes at least 1 minute. Use `tenacity` (already in `requirements.txt`) for exponential backoff on `ResourceExhausted` errors. Batch document ingestion should be an offline/async operation, not part of the synchronous upload request.

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=GEMINI_API_KEY,
    task_type="retrieval_document",  # use retrieval_query for query-time
)
# Returns list of float vectors, dimension=3072 by default
# Set output_dimensionality in request kwargs if needed
```

**What NOT to use:**
- OpenAI `text-embedding-ada-002`: costs money.
- Hugging Face sentence-transformers locally: cold-start model load on Vercel serverless = 10–30 second first-request latency, likely hits function timeout.
- `text-embedding-004`: This is the old name; the current free model is `gemini-embedding-001`.

**Confidence: LOW** (rate limits are approximate from community sources; verify in AI Studio before building ingestion pipeline)

### 3d. Vector Store

**Recommended: Supabase pgvector via `vecs` client**

| Library | Version | Purpose |
|---------|---------|---------|
| `vecs` | `>=0.4` | Postgres/pgvector Python client — collection management, upsert, HNSW indexing, semantic search |

```python
import vecs

# Connect (use DIRECT URL for schema setup; POOLER URL for queries)
vx = vecs.create_client(SUPABASE_DIRECT_URL)

# Create collection (once)
docs = vx.get_or_create_collection(name="doc_chunks", dimension=768)

# Ingest: (id, vector, metadata_dict)
docs.upsert(records=[
    (chunk_id, embedding_vector, {"doc_id": doc_id, "chunk_index": i, "session_id": session_id})
])

# Create HNSW index (after first batch or at collection creation)
from vecs import IndexMethod, IndexMeasure
docs.create_index(method=IndexMethod.hnsw, measure=IndexMeasure.cosine_distance)

# Query at retrieval time
results = docs.query(
    data=query_embedding,
    limit=5,
    filters={"session_id": {"$eq": session_id}},  # isolate per-user docs
    include_metadata=True,
)
```

**HNSW vs IVFFlat:**
- **Use HNSW.** Higher recall, can be created before or after data is loaded, and performs better at query time. At the scale of a portfolio demo (<10K chunks), HNSW has no meaningful downside.
- IVFFlat must be created after data is loaded to avoid reduced recall, and offers no advantage for small collections.

**Supabase pgvector setup (run once via Supabase dashboard SQL editor):**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
pgvector is pre-installed on Supabase; the extension just needs to be enabled.

**Why not LangChain's PGVector class:** It works but adds a layer of abstraction with its own table schema. `vecs` maps more directly to Supabase's approach and is the officially recommended client for Supabase AI workloads. Either is viable.

**Why not Pinecone/Qdrant free tiers:** Pinecone free is limited to 1 index; Qdrant free is cloud-only with limited storage. Supabase unifies all persistence in one place and stays on the existing Postgres connection.

**Confidence: MEDIUM** (vecs API confirmed against Supabase docs; Supabase pgvector compatibility confirmed)

---

## Pillar 4 — MCP (Model Context Protocol)

### Transport Selection (Critical)

SSE transport was deprecated by the MCP project in December 2025. The current standard is **Streamable HTTP**. All new MCP work should use Streamable HTTP. Do not build against SSE.

Streamable HTTP works natively with Vercel Python serverless: it is a standard HTTP POST endpoint that optionally streams responses. No long-lived processes needed.

### Hosting an MCP Server (Exposing Agent Tools)

**Recommended: `fastmcp` + existing FastAPI app**

| Library | Version | Purpose |
|---------|---------|---------|
| `fastmcp` | `>=2.0` | Fast, Pythonic MCP server framework; FastMCP 1.0 was incorporated into the official MCP SDK |

FastMCP creates a Streamable HTTP MCP server as a FastAPI sub-application, mountable on the existing `api.py`:

```python
from fastmcp import FastMCP

mcp = FastMCP("ReAct Agent Tools")

@mcp.tool()
async def web_search(query: str) -> str:
    """Search the web for current information."""
    ...

# Mount on existing FastAPI app at /mcp
app.mount("/mcp", mcp.streamable_http_app())
```

This exposes the agent's tools as an MCP server over Streamable HTTP at `/api/mcp`, making the agent consumable by Claude Desktop, Cursor, and other MCP clients.

### Consuming MCP Tools in the Agent

**Recommended: `langchain-mcp-adapters`**

| Library | Version | Purpose |
|---------|---------|---------|
| `langchain-mcp-adapters` | `>=0.1` | Converts MCP tools to LangChain-compatible tools for LangGraph agents |

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "external_tool_server": {
        "transport": "streamable_http",
        "url": "https://some-mcp-server.com/mcp",
    }
})
tools = await client.get_tools()
# tools is a list of standard LangChain BaseTool objects
```

**What NOT to use:**
- stdio transport: requires a long-lived subprocess. Incompatible with Vercel serverless.
- SSE transport: deprecated. Legacy integrations only.
- Custom HTTP client parsing: the official SDK handles all MCP protocol negotiation.

**Version requirements for MCP ecosystem:**
- `mcp >= 1.6` (official SDK; transitively required by langchain-mcp-adapters)
- `langgraph >= 0.3` (required by langchain-mcp-adapters; will drive the LangGraph upgrade)

**Confidence: MEDIUM** (langchain-mcp-adapters pattern confirmed; fastmcp Vercel deployment confirmed by community. Exact API surface may shift as MCP spec finalizes the Streamable HTTP spec released June 2026.)

---

## Pillar 5 — Observability

### Trace Persistence

The existing in-memory trace store (`deque`, last 100 runs) already produces the Step schema (thought / action / observation / final). The observability upgrade persists this to Supabase and adds a dashboard.

**Persistence: native Supabase (no extra library)**. Write traces as JSONB to a `agent_runs` table using the existing psycopg3 connection. This is the lowest-complexity option and avoids adding a third-party observability dependency on the critical path.

```sql
CREATE TABLE IF NOT EXISTS agent_runs (
    id         TEXT PRIMARY KEY,
    session_id TEXT,
    query      TEXT,
    steps      JSONB,
    usage      JSONB,
    status     TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON agent_runs (session_id, created_at DESC);
```

### LLM Tracing / Structured Observability

**Recommended: Langfuse cloud free tier**

| Library | Version | Purpose |
|---------|---------|---------|
| `langfuse` | `>=4.12.0` | LLM-native observability: traces, token costs, LangChain callbacks |

Langfuse cloud free tier (Hobby plan):
- 50,000 billable units/month (1 unit = any trace event: span, generation, score)
- 30-day data retention
- 2 users
- No credit card required

LangChain/LangGraph integration:

```python
from langfuse.langchain import CallbackHandler  # SDK v4 import path

langfuse_handler = CallbackHandler(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    host="https://cloud.langfuse.com",
)

# Pass to graph invocation:
result = await graph.ainvoke(state, config={
    "configurable": {"thread_id": session_id},
    "callbacks": [langfuse_handler],
})
```

**SDK v4 breaking change:** `langfuse.decorators` module was removed in v4. Use `from langfuse import observe, get_client` for decorator-based tracing. The LangChain callback import path is `from langfuse.langchain import CallbackHandler`.

**Why Langfuse over LangSmith:** LangSmith free tier is 5,000 traces/month. Langfuse is 50,000/month — 10x more generous. Both are free; Langfuse wins on limits.

**Why not self-host Langfuse:** Self-hosting requires Docker Compose (two application containers + storage). Not compatible with Vercel serverless. A separate VM would be needed, which costs money.

**Fallback if Langfuse quota is exhausted:** The self-built Supabase trace table (above) always runs. Langfuse is additive, not critical-path.

### Supabase Keep-Alive (Inactivity Pause Prevention)

The Supabase free tier pauses after 7 days of inactivity. Mitigation: a Vercel cron job pings the database every 5 days.

**Vercel Hobby allows exactly 1 cron job.** Use it for keep-alive. The cron makes a lightweight query (e.g., `SELECT 1`) to keep the project alive. Configure in `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/health",
      "schedule": "0 0 */5 * *"
    }
  ]
}
```

The existing `/health` endpoint already exists; it just needs to touch the database. No extra infrastructure required.

**Confidence: MEDIUM** (Langfuse pricing confirmed from their pricing page; keep-alive pattern widely confirmed by community)

---

## New Packages Summary

All packages below are additive. Install into `backend/requirements.txt`.

```bash
# Persistence backbone
psycopg[binary]>=3.2.0
psycopg-pool>=3.2.0

# LangGraph persistence (upgrade LangGraph first, verify compatibility)
langgraph-checkpoint-postgres>=3.1.0

# Embeddings
langchain-google-genai>=2.0.0

# RAG document parsing
pymupdf4llm>=0.0.17
python-docx>=1.1.0

# Vector store
vecs>=0.4.0

# MCP
mcp>=1.6.0
fastmcp>=2.0.0
langchain-mcp-adapters>=0.1.0

# Observability
langfuse>=4.12.0
```

**Python 3.11 compatibility:** All packages above support Python 3.11. No Python version change needed.

---

## Environment Variables (New)

Add to `.env` and Vercel environment:

```bash
# Supabase
SUPABASE_DB_URL=postgresql://postgres.[ref]:[pass]@db.[ref].supabase.co:5432/postgres  # direct, migrations only
SUPABASE_POOLER_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres  # serverless queries

# Langfuse (optional but recommended)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

---

## Alternatives Rejected

| Category | Rejected | Reason |
|----------|----------|--------|
| Vector store | Pinecone (free) | 1 index limit, separate service to manage |
| Vector store | Qdrant cloud free | Separate service; Supabase already unifies persistence |
| Embeddings | sentence-transformers (local) | Cold-start model load ~10–30s on Vercel; exceeds acceptable first-request latency |
| Embeddings | OpenAI embeddings | Costs money — violates $0 constraint |
| DB driver | asyncpg | Prepared-statement incompatibility with Supabase PgBouncer transaction mode |
| MCP transport | stdio | Requires long-lived subprocess; incompatible with serverless |
| MCP transport | SSE | Deprecated Dec 2025 by MCP project |
| Observability | LangSmith | 5k traces/month free vs Langfuse 50k; strictly worse for this use case |
| Observability | Self-hosted Langfuse | Requires Docker Compose; no free serverless host |
| Doc parsing | unstructured | Heavy deps (LibreOffice optional), slow, install issues on Vercel |
| Chunking | Semantic chunking | Requires LLM call per boundary; burns free quota |

---

## Confidence Summary

| Area | Confidence | Limiting Factor |
|------|------------|-----------------|
| Supabase pgvector + vecs | MEDIUM | API confirmed; free tier limits verified |
| psycopg3 pooler connection | MEDIUM | Community-confirmed; specific connection string format needs testing |
| LangGraph checkpoint-postgres | LOW | Version compatibility with existing langgraph 0.2.45 unverified |
| Gemini embedding-001 rate limits | LOW | "~100 RPM, ~1000 RPD" is approximate; check AI Studio for actual project limits |
| MCP Streamable HTTP + fastmcp | MEDIUM | Pattern confirmed; MCP spec RC released June 2026, minor API changes possible |
| Langfuse free tier | MEDIUM | Pricing page confirmed; SDK v4 import paths confirmed |
| Keep-alive cron strategy | HIGH | Multiple independent community confirmations; straightforward implementation |

---

*Research date: 2026-06-29. Verify all version pins at implementation time — this ecosystem moves fast.*
