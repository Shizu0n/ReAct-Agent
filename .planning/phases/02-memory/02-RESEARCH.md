# Phase 2: Memory — Research

**Researched:** 2026-06-29
**Domain:** LangGraph checkpointer (PostgresSaver) + long-term store (PostgresStore) on Supabase Supavisor transaction pooler; memory-as-visible-tools pattern; anonymous session identity; clear-memory endpoint
**Confidence:** MEDIUM (core patterns verified directly against installed library source code; Supabase pipeline-mode compatibility confirmed via official docs + GitHub issues; some connection details are environment-specific)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEM-01 | Frontend sends anonymous session id (X-Session-Id header) on every agent run | Session ID stored in localStorage, sent as header, extracted in FastAPI from `request.headers.get("x-session-id")` |
| MEM-02 | Conversation history persists across browser sessions via PostgresSaver checkpointer | `AsyncPostgresSaver(conn=pool)` + `compile(checkpointer=...)` + `config={"configurable":{"thread_id":session_id}}`. Verified: `adelete_thread`, `setup()` tables confirmed. |
| MEM-03 | Agent stores salient long-term facts and references them in later responses | `AsyncPostgresStore(conn=pool)` + `memory_read`/`memory_write` tool handlers in `tool_node` with `store: BaseStore` injection |
| MEM-04 | Memory reads/writes appear as named steps in reasoning trace | Handle `memory_read`/`memory_write` in `tool_node` → create `Step` dicts → emit via SSE (same path as calculator/web_search). Not hidden pipeline operations. |
| MEM-05 | Current session id visible and copyable in UI | Small UI element (chip/badge) in chat header or sidebar, reads from component state initialized from localStorage |
| MEM-06 | User can clear/reset all memory for session | `DELETE /api/memory/{session_id}` endpoint: `checkpointer.adelete_thread(session_id)` + raw SQL `DELETE FROM store WHERE prefix LIKE 'memories.{session_id}%'` |
| MEM-07 | Stored memory capped (top-N by recency) | At write time: `store.asearch(namespace, limit=N)` → `store.adelete(...)` oldest → `store.aput(...)` new. Non-vector search returns `ORDER BY updated_at DESC`. |
</phase_requirements>

---

## Summary

Phase 2 adds two memory layers to the existing 2-node LangGraph agent: **short-term memory** (conversation history across browser reloads) via `AsyncPostgresSaver`, and **long-term semantic memory** (cross-session fact recall) via `AsyncPostgresStore`. Both persistence layers already have their tables created via `setup()` calls (which are idempotent). The existing `backend/agent/db.py` connection factory (Phase 1) provides the correct pooler settings.

The most important architectural decision in this phase is **memory as visible tools, not a silent pipeline**. The project's core differentiator is that tool calls appear as discrete Steps in the reasoning trace. Adding `memory_read` and `memory_write` to `TOOL_SCHEMAS` and handling them in `tool_node` gives memory the same trace visibility as `calculator` and `web_search` — with zero new trace infrastructure.

The most important technical risk is **`from_conn_string` is not safe for Supabase transaction pooler**. It hard-codes `prepare_threshold=0` which uses prepared statements. The Supabase docs explicitly recommend `prepare_threshold=None` for psycopg3 with transaction pooler. The correct pattern is to pass an `AsyncConnectionPool` (with `prepare_threshold=None` in its kwargs) directly to the constructors. Additionally, `supports_pipeline` must be set to `False` on both the checkpointer and store objects because psycopg3's pipeline mode is unreliable on Supavisor transaction pooler. [CITED: supabase.com/docs/guides/troubleshooting/disabling-prepared-statements]

The second important operational constraint is the **Vercel requirements drift**: `api/requirements.txt` is still on the old pre-upgrade versions (`langgraph==0.2.45`, `langchain-core==0.3.63`). Phase 2 will 500 in production unless `api/requirements.txt` is brought up to match `backend/requirements.txt`. This must be the first task of Wave 1.

**Primary recommendation:** Implement memory as tools (`memory_read`/`memory_write` in TOOL_SCHEMAS + handled in `tool_node`), use `AsyncConnectionPool` with `prepare_threshold=None`, set `supports_pipeline=False`, and fix `api/requirements.txt` before deploying any Phase 2 code.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session ID generation | Browser / Client (`useAgent.ts` localStorage) | — | Must survive across page reloads; no server-side user identity |
| Session ID propagation | API / Backend (`api.py` header extraction) | — | `request.headers.get("x-session-id")` → thread config |
| Short-term memory (conversation history) | API / Backend (`AsyncPostgresSaver`) | Database / Storage (Supabase) | LangGraph checkpointer restores messages on each invoke |
| Long-term memory (cross-session facts) | API / Backend (`AsyncPostgresStore` + `tool_node`) | Database / Storage (Supabase) | Facts written/read via store; appear in trace |
| Memory visibility in trace | API / Backend (`tool_node` Step creation) | — | Same Step pipeline as all other tools; no new SSE logic |
| Session ID display in UI | Browser / Client (React component) | — | Read from state, copy-to-clipboard button |
| Clear memory endpoint | API / Backend (`DELETE /api/memory/{session_id}`) | Database / Storage | Deletes checkpoint rows + store rows for session |
| Memory recency cap (MEM-07) | API / Backend (`tool_node` write handler) | — | At write time: check count, evict oldest |
| Connection pool lifecycle | API / Backend (FastAPI lifespan or per-request) | — | See pitfall section; pool or per-request pattern |
| `api/requirements.txt` sync | API / Backend (Vercel build) | — | Vercel deploys from this file; must be kept in sync |

---

## Standard Stack

### Core — Phase 2 Uses (already installed in backend/requirements.txt)

| Library | Installed Version | Purpose | Import Path |
|---------|-----------------|---------|-------------|
| `langgraph-checkpoint-postgres` | 3.1.0 [VERIFIED: pip freeze from Phase 1] | Short-term memory via `AsyncPostgresSaver` | `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver` |
| `langgraph.store.postgres` | (part of langgraph 1.2.6) [VERIFIED: pip freeze] | Long-term memory via `AsyncPostgresStore` | `from langgraph.store.postgres import AsyncPostgresStore` |
| `psycopg[binary]` | 3.3.4 [VERIFIED: pip freeze] | Async Postgres driver | `from psycopg import AsyncConnection` |
| `psycopg-pool` | 3.3.1 [VERIFIED: pip freeze] | Connection pool for per-request checkout | `from psycopg_pool import AsyncConnectionPool` |
| `langgraph.store.base` | (part of langgraph 1.2.6) | `BaseStore` type for node injection | `from langgraph.store.base import BaseStore` |

### What MUST Be Added to api/requirements.txt (Vercel Deployment Gap)

`api/requirements.txt` is on the pre-upgrade versions. Phase 2 will fail in production until this is fixed.

| Package | Current in api/requirements.txt | Required |
|---------|-------------------------------|---------|
| `langgraph` | `==0.2.45` | `>=1.2.6` |
| `langchain-core` | `==0.3.63` | `>=1.4.8` |
| `langchain` | not present | `>=1.3.11` |
| `langchain-community` | not present | `>=0.4.2` |
| `langgraph-checkpoint-postgres` | not present | `>=3.1.0` |
| `psycopg-pool` | not present | `>=3.2.0` |
| `langsmith` | not present | `>=0.9.3` |

The complete `api/requirements.txt` should mirror the entries from `backend/requirements.txt` that are needed by the Vercel Python function. In practice: replace the entire file contents with the same minimum-version constraints as `backend/requirements.txt`. [ASSUMED — best practice; confirm no Vercel-specific exclusions needed]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Memory as tools in `tool_node` | Silent pre/post pipeline in `agent_node` | Silent pipeline violates MEM-04 (must appear as trace Steps). Tool path is architecturally consistent with existing code. |
| `AsyncConnectionPool` at lifespan | Per-request `AsyncConnection` | Pool: connection reuse (more efficient, handles reconnects). Per-request: simpler but reconnects on every request. Pool is preferred. |
| `AsyncConnectionPool` at lifespan | `from_conn_string` class method | `from_conn_string` hard-codes `prepare_threshold=0` which breaks Supavisor. Always bypass it. |
| Recency cap at write time | Recency cap at read time (LIMIT N in search) | Read-time cap is simpler but store grows unbounded. Write-time cap keeps the table bounded at N entries per session. Either satisfies MEM-07; write-time is safer. |

**Installation note:** No new pip installs needed in `backend/requirements.txt` — all packages were installed in Phase 1. The only installation work is updating `api/requirements.txt` for Vercel.

---

## Package Legitimacy Audit

All packages were verified in Phase 1. Repeating for completeness:

| Package | Registry | Source Repo | Verdict | Disposition |
|---------|----------|-------------|---------|-------------|
| `langgraph-checkpoint-postgres` | PyPI | github.com/langchain-ai/langgraph | SUS (unknown downloads) | Approved — official LangChain AI subproject |
| `psycopg` | PyPI | psycopg.org | SUS (unknown downloads) | Approved — canonical PostgreSQL Python driver |
| `psycopg-pool` | PyPI | psycopg.org | SUS (unknown downloads) | Approved — companion package same org |
| `langgraph.store.postgres` | (included in langgraph package) | github.com/langchain-ai/langgraph | OK | Approved — same package as langgraph |

**Packages removed due to SLOP verdict:** none
**Packages flagged SUS (requires user action):** none — false positives as in Phase 1

---

## Architecture Patterns

### System Architecture Diagram

```
[Browser]
  localStorage: session_id (UUID, persistent)
  localStorage: react-agent:chat-session:v1 (messages, steps)
         |
         | POST /api/run
         | Header: X-Session-Id: {session_id}
         | Body: {query, stream, history}
         v
[FastAPI api.py]
  run_agent() or _stream_agent()
    session_id = request.headers.get("x-session-id") or uuid4()
    config = {"configurable": {"thread_id": session_id}}
         |
         v
  [Connection Pool (module-level or lifespan)]
    AsyncConnectionPool(SUPABASE_POOLER_URL,
      kwargs={prepare_threshold:None, autocommit:True, row_factory:dict_row})
         |
         +--> AsyncPostgresSaver(conn=pool)  [short-term memory]
         |    supports_pipeline = False
         |
         +--> AsyncPostgresStore(conn=pool)  [long-term memory]
              supports_pipeline = False
         |
         v
  build_graph(checkpointer=checkpointer, store=store)
  graph.stream(initial_state, config=config, stream_mode="values")
         |
         v
[LangGraph StateGraph]
  START
    -> agent_node(state, store: BaseStore)
         - Reads long-term memories from store (namespace=("memories", session_id))
         - Injects memories into system prompt
         - Calls LLM with TOOL_SCHEMAS (includes memory_read, memory_write)
    -> tool_node(state, store: BaseStore)
         - For memory_read: store.asearch(namespace, limit=N) -> observation
         - For memory_write: store.aput(namespace, key, {"text": fact})
           with recency cap: search -> delete oldest if N reached
         - Creates Step for each tool call (same as calculator/web_search)
         - Steps emitted via SSE as thought/action/observation
    -> END (final_answer set)
         |
         v
  [Postgres: Supabase pooler port 6543]
    checkpoints table        <- thread_id = session_id (short-term memory)
    checkpoint_blobs table   <- thread_id = session_id
    checkpoint_writes table  <- thread_id = session_id
    store table              <- prefix = "memories.{session_id}" (long-term)
    store_migrations table
    checkpoint_migrations table

[DELETE /api/memory/{session_id}]
  checkpointer.adelete_thread(session_id)  <- deletes checkpoint rows
  raw SQL: DELETE FROM store WHERE prefix LIKE 'memories.{session_id}%'
  -> frontend clears localStorage messages + steps

[GET /api/config → AgentConfigResponse now includes session_id? No — session_id is client-owned]
```

### Recommended Project Structure (new and modified files)

```
backend/
├── agent/
│   ├── db.py              (EDIT) — add create_pool() factory returning AsyncConnectionPool
│   ├── graph.py           (EDIT) — build_graph() takes checkpointer/store; add memory tools to TOOL_SCHEMAS/TOOL_INPUT_KEYS; tool_node gets store:BaseStore
│   ├── prompts.py         (EDIT) — add memory context injection to system prompt
│   └── tools.py           (unchanged — memory_read/memory_write are NOT @tool functions)
├── api.py                 (EDIT) — extract X-Session-Id; create pool in lifespan; call setup(); DELETE /memory/{session_id} endpoint
├── requirements.txt       (unchanged — all packages already present)
api/
└── requirements.txt       (EDIT — CRITICAL — sync to match backend/requirements.txt)
frontend/src/
└── hooks/useAgent.ts      (EDIT) — generate+persist session_id in localStorage; send X-Session-Id header; expose session_id in state
frontend/src/
└── components/demo/
    └── ChatPanel.tsx      (EDIT) — display session_id badge with copy button; "Clear Memory" button
```

### Pattern 1: AsyncConnectionPool with Supabase-Safe Settings

**What:** Create an `AsyncConnectionPool` with `prepare_threshold=None` and `autocommit=True`. This is the only safe pattern for Supabase Supavisor transaction pooler (port 6543). Do NOT use `from_conn_string` — it hard-codes `prepare_threshold=0`.

**When to use:** At FastAPI lifespan startup; store pool in `app.state`; reuse per request.

```python
# backend/agent/db.py — add after existing pooler_connection()
# Source: Verified against AsyncConnectionPool docs and Supabase troubleshooting docs

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

async def create_pool(min_size: int = 1, max_size: int = 3) -> AsyncConnectionPool:
    """Create an async connection pool safe for Supabase Supavisor transaction mode.
    
    Key settings:
    - prepare_threshold=None: completely disables prepared statements (required for port 6543)
    - autocommit=True: required by AsyncPostgresSaver/AsyncPostgresStore
    - row_factory=dict_row: required by AsyncPostgresSaver/AsyncPostgresStore
    - max_size=3: small pool; Vercel functions handle 1 request at a time
    """
    pool = AsyncConnectionPool(
        conninfo=_pooler_url(),
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "prepare_threshold": None,   # REQUIRED: disables prepared statements for Supavisor
            "autocommit": True,           # REQUIRED: AsyncPostgresSaver/Store
            "row_factory": dict_row,      # REQUIRED: AsyncPostgresSaver/Store
        },
        open=False,  # do not open immediately; caller opens it
    )
    return pool
```

### Pattern 2: Checkpointer and Store Construction

**What:** Construct `AsyncPostgresSaver` and `AsyncPostgresStore` from the pool and force `supports_pipeline=False` to avoid Supavisor pipeline mode incompatibility. [ASSUMED re: pipeline; known to fail on some Supavisor versions per GitHub issue #2407 / #5675]

```python
# Source: Verified against AsyncPostgresSaver source code (langgraph-checkpoint-postgres 3.1.0)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

def build_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(conn=pool)
    checkpointer.supports_pipeline = False  # force conn.transaction() not conn.pipeline()
    return checkpointer

def build_store(pool: AsyncConnectionPool) -> AsyncPostgresStore:
    store = AsyncPostgresStore(conn=pool)
    store.supports_pipeline = False  # same reason
    return store
```

### Pattern 3: FastAPI Lifespan for Pool + Setup

**What:** Open the pool and run `setup()` once at cold-start. Store objects in `app.state` for reuse.

```python
# backend/api.py — replace the existing module-level startup with a lifespan
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent.db import create_pool, build_checkpointer, build_store
    pool = await create_pool()
    await pool.open()
    
    checkpointer = build_checkpointer(pool)
    store = build_store(pool)
    
    # setup() is idempotent (IF NOT EXISTS); safe to call on every cold start
    await checkpointer.setup()
    await store.setup()
    
    app.state.pool = pool
    app.state.checkpointer = checkpointer
    app.state.store = store
    
    yield  # app runs
    
    await pool.close()

app = FastAPI(title="01 React Agent API", lifespan=lifespan)
```

### Pattern 4: Graph Compilation with Checkpointer and Store

**What:** `build_graph()` now accepts (and requires) checkpointer and store. The graph is compiled once per cold start and reused (thread-safe for reads; checkpointer/store handle per-thread isolation).

```python
# backend/agent/graph.py — modified build_graph()
# Source: Verified against StateGraph.compile() signature (langgraph 1.2.6)

def build_graph(llm=None, tracker=None, checkpointer=None, store=None):
    active_llm = llm or _create_default_llm()
    if tracker is not None:
        active_llm = UsageTrackingLLM(active_llm, tracker)
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_node", lambda state: agent_node(state, active_llm))
    workflow.add_node("tool_node", tool_node)  # tool_node gets store via injection
    workflow.add_edge(START, "agent_node")
    workflow.add_conditional_edges(
        "agent_node",
        should_continue,
        {"tools": "tool_node", "end": END},
    )
    workflow.add_edge("tool_node", "agent_node")
    return workflow.compile(checkpointer=checkpointer, store=store)
```

### Pattern 5: Session ID Extraction in api.py

**What:** Extract `X-Session-Id` from the request header. Fall back to a new UUID if absent (anonymous visitor who hasn't sent a session ID yet).

```python
# backend/api.py — in run_agent() and stream_agent()
# Source: FastAPI Request object, request.headers dict

def _get_session_id(request: Request) -> str:
    session_id = request.headers.get("x-session-id", "").strip()
    return session_id if session_id else str(uuid.uuid4())

def _graph_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}
```

### Pattern 6: memory_read and memory_write as Tool Handlers

**What:** Add `memory_read` and `memory_write` to `TOOL_SCHEMAS` and `TOOL_INPUT_KEYS`. In `tool_node`, detect these names and handle them inline using the injected `store: BaseStore`. This gives full trace visibility (Step creation) without a separate tool class.

**When to use:** Whenever the LLM determines a memory operation is appropriate.

```python
# backend/agent/graph.py additions
# Source: KWARGS_CONFIG_KEYS verified in langgraph._internal._runnable source

MEMORY_READ_TOOL_NAME = "memory_read"
MEMORY_WRITE_TOOL_NAME = "memory_write"
MEMORY_NAMESPACE_PREFIX = "memories"  # store prefix: "memories.{session_id}"
MAX_MEMORIES_STORED = 20              # MEM-07: top-N cap

# Add to TOOL_INPUT_KEYS:
TOOL_INPUT_KEYS = {
    ...existing...,
    MEMORY_READ_TOOL_NAME: "query",
    MEMORY_WRITE_TOOL_NAME: "content",
}

# Add to TOOL_SCHEMAS:
{
    "type": "function",
    "function": {
        "name": MEMORY_READ_TOOL_NAME,
        "description": (
            "Read facts the user has shared in previous sessions. Call this at the start "
            "of any conversation where you detect the user refers to a past interaction "
            "or where you want to personalize your response. Returns stored facts ordered "
            "by recency."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Brief description of what to recall."}
            },
            "required": ["query"],
        },
    },
},
{
    "type": "function",
    "function": {
        "name": MEMORY_WRITE_TOOL_NAME,
        "description": (
            "Store a fact the user has shared for recall in future sessions. Call this when "
            "the user shares personal information, preferences, goals, or facts they want "
            "the agent to remember. Store one discrete fact per call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The fact to remember, written as a brief statement."}
            },
            "required": ["content"],
        },
    },
},

# Modified tool_node to accept store injection:
def tool_node(state: AgentState, store: BaseStore) -> dict[str, Any]:
    ...
    # Handle memory_read inline:
    if action == MEMORY_READ_TOOL_NAME:
        observation = _run_memory_read(store, session_id, action_input)
    elif action == MEMORY_WRITE_TOOL_NAME:
        observation = _run_memory_write(store, session_id, action_input)
    else:
        observation = _run_tool(action, action_input)
```

**Store node injection:** Adding `store: BaseStore` to `tool_node`'s signature triggers automatic injection when compiled with `store=store`. [VERIFIED: KWARGS_CONFIG_KEYS source in langgraph._internal._runnable]

**Session ID in tool_node:** `tool_node` needs the session_id to namespace the store. Obtain it from the graph config: `config["configurable"]["thread_id"]`. Add `config: RunnableConfig` to the node signature (also injectable via KWARGS_CONFIG_KEYS).

### Pattern 7: Memory Read and Write Implementations

```python
# backend/agent/graph.py — memory helper functions
# Source: AsyncPostgresStore API verified from source code

async def _run_memory_read(store: BaseStore, session_id: str, query: str) -> str:
    namespace = (MEMORY_NAMESPACE_PREFIX, session_id)
    items = await store.asearch(namespace, limit=MAX_MEMORIES_STORED)
    if not items:
        return "No memories found for this session."
    facts = [item.value.get("text", "") for item in items if item.value.get("text")]
    return "Recalled memories:\n" + "\n".join(f"- {f}" for f in facts)

async def _run_memory_write(store: BaseStore, session_id: str, content: str) -> str:
    namespace = (MEMORY_NAMESPACE_PREFIX, session_id)
    # Enforce top-N cap: evict oldest if at limit
    existing = await store.asearch(namespace, limit=MAX_MEMORIES_STORED + 1)
    if len(existing) >= MAX_MEMORIES_STORED:
        # existing is sorted by updated_at DESC; last item is oldest
        oldest = existing[-1]
        await store.adelete(namespace, oldest.key)
    import uuid as uuid_mod
    key = str(uuid_mod.uuid4())
    await store.aput(namespace, key, {"text": content})
    return f"Stored: {content}"
```

Note: `tool_node` is currently synchronous. Memory operations are async. Two options:
1. Make `tool_node` an async function: `async def tool_node(state, store, config)` — preferred; LangGraph supports async nodes
2. Use `asyncio.run()` in sync context — not compatible with async event loop

**Recommended:** make `tool_node` async (add `async def`). [ASSUMED this is compatible with existing graph wiring; verify tests pass]

### Pattern 8: Clear Memory Endpoint

```python
# backend/api.py — new endpoint
# Source: AsyncPostgresSaver.adelete_thread() verified from source code

@app.delete("/memory/{session_id}")
@app.delete("/api/memory/{session_id}")
async def clear_memory(session_id: str, request: Request) -> dict:
    checkpointer = request.app.state.checkpointer
    store = request.app.state.store
    
    # 1. Clear conversation history (checkpoint tables)
    await checkpointer.adelete_thread(session_id)
    
    # 2. Clear long-term memories (store table)
    # No bulk-delete-by-namespace API exists; use raw SQL via the pool
    pool = request.app.state.pool
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM store WHERE prefix LIKE %s",
            (f"{MEMORY_NAMESPACE_PREFIX}.{session_id}%",),
        )
    
    return {"status": "cleared", "session_id": session_id}
```

**Vercel.json rewrite:** Add `/memory` bare path rewrite per the CLAUDE.md dual-registration convention.

### Pattern 9: Frontend Session ID Management

```typescript
// frontend/src/hooks/useAgent.ts additions

const SESSION_ID_KEY = 'react-agent:session-id'

function getOrCreateSessionId(): string {
  const existing = window.localStorage.getItem(SESSION_ID_KEY)
  if (existing) return existing
  const id = crypto.randomUUID()
  window.localStorage.setItem(SESSION_ID_KEY, id)
  return id
}

// In runApi(), add to headers:
headers: {
  'Content-Type': 'application/json',
  'X-Session-Id': getOrCreateSessionId(),
}

// Expose via useAgent return value:
return { state, sendQuery, clearHistory, sessionId: getOrCreateSessionId() }
```

**Clear memory from UI:** The existing `clearHistory()` clears localStorage messages. For MEM-06, it should also:
1. Call `DELETE /api/memory/{session_id}` 
2. Optionally clear and regenerate the session_id (if user wants a truly fresh session)
3. Per spec: clear memory for the CURRENT session_id, not necessarily rotate it

### Anti-Patterns to Avoid

- **Using `from_conn_string`:** Hard-codes `prepare_threshold=0`, breaks on Supavisor transaction mode. Always bypass it and construct directly.
- **Memory as hidden pipeline in `agent_node`:** Violates MEM-04. Memory operations must appear as tool Steps.
- **Module-level singleton connection (not pool):** Single async connection can't be shared across coroutines without a lock; pool handles this correctly.
- **Not setting `supports_pipeline=False`:** `aput()` tries `conn.pipeline()` which may fail on Supavisor with `psycopg.OperationalError: SSL connection closed unexpectedly` or similar. [CITED: github.com/langchain-ai/langgraph/issues/5675]
- **Calling `setup()` only once and then forgetting:** `setup()` is idempotent. Calling it on every cold start is safe and ensures tables exist after a Supabase resume.
- **Not updating `api/requirements.txt`:** The Vercel Python function builds from this file. Missing packages → production 500s.
- **Passing session_id directly in request body:** Should be a header (`X-Session-Id`), not a body field, to keep the session concept orthogonal to the query payload.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Conversation history across sessions | Custom messages table + manual restore | `AsyncPostgresSaver` + `compile(checkpointer=...)` + `thread_id` | Checkpointer handles serialization, versioning, concurrent writes, and restoration via `aget_tuple()` |
| Per-session fact store | Custom table with manual serialization | `AsyncPostgresStore.aput/asearch` | Store handles namespace isolation, JSONB serialization, recency ordering, and TTL |
| Bulk namespace delete in store | Custom `_namespace_to_text` + DELETE query | raw SQL `DELETE FROM store WHERE prefix LIKE %s` | Store has no bulk-delete API; direct SQL is correct for this one-off operation |
| Prepared-statement-safe pool | Custom connection factory with prepared statements | `AsyncConnectionPool` with `prepare_threshold=None` | Pool handles reconnects, max connections, and correct settings centrally |
| Thread deletion | Manual DELETE on checkpoint tables | `checkpointer.adelete_thread(session_id)` | Handles all three tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) atomically |

**Key insight:** The store and checkpointer are designed specifically for LangGraph agent patterns. Fighting them (bypassing, reimplementing) costs significant complexity for zero benefit.

---

## Common Pitfalls

### Pitfall 1: `from_conn_string` Uses Wrong Prepared Statement Setting

**What goes wrong:** `AsyncPostgresSaver.from_conn_string(url)` connects with `prepare_threshold=0`, meaning psycopg3 immediately prepares every statement. When Supavisor routes the next query to a different backend, the prepared statement `_pg3_0` does not exist there. Error: `psycopg.errors.InvalidSqlStatementName`.

**Why it happens:** The library default is intended for single-server Postgres. Supabase Supavisor transaction mode routes each transaction to a different backend, so server-side prepared statement caches are not shared.

**How to avoid:** Never call `from_conn_string`. Construct `AsyncConnectionPool` directly with `prepare_threshold=None` in its kwargs, then pass the pool to `AsyncPostgresSaver(conn=pool)`.

**Warning signs:** `psycopg.errors.InvalidSqlStatementName: prepared statement "_pg3_0" does not exist` — intermittent; appears after the first few requests.

**Source:** [CITED: supabase.com/docs/guides/troubleshooting/disabling-prepared-statements]

### Pitfall 2: Pipeline Mode Fails on Supavisor Transaction Pooler

**What goes wrong:** `AsyncPostgresSaver.__init__()` sets `self.supports_pipeline = Capabilities().has_pipeline()` which returns `True` when libpq >= 14. The `aput()` method then calls `_cursor(pipeline=True)` → `conn.pipeline()`. Supavisor transaction mode does not fully support psycopg3 pipeline protocol in all versions. Error: `psycopg.OperationalError: SSL connection has been closed unexpectedly` or `psycopg.OperationalError: consuming input failed`.

**Why it happens:** Pipeline mode sends multiple queries before reading responses, assuming all queries go to the same backend process. Supavisor transaction mode can route queries to different backends.

**How to avoid:** After constructing the checkpointer and store, set `checkpointer.supports_pipeline = False` and `store.supports_pipeline = False`. This forces `_cursor` to use `conn.transaction()` instead of `conn.pipeline()`.

**Warning signs:** Connection errors after the first successful `aput()` call; errors correlate with checkpoint writes not reads. [CITED: github.com/langchain-ai/langgraph/issues/5675, github.com/langchain-ai/langgraph/issues/2407]

**Uncertainty:** This pitfall is documented in GitHub issues and Supabase community reports but is environment-dependent. Supabase may have improved Supavisor pipeline compatibility in recent versions. Test explicitly and document the result.

### Pitfall 3: `tool_node` Needs Config to Get session_id for Namespace

**What goes wrong:** `tool_node` handles `memory_read`/`memory_write` inline and needs the session_id to construct the namespace `("memories", session_id)`. But `tool_node(state, store)` doesn't have the session_id directly.

**How to avoid:** Add `config: RunnableConfig` to `tool_node`'s signature. LangGraph injects the config automatically. Extract `session_id = config["configurable"]["thread_id"]`.

```python
from langchain_core.runnables import RunnableConfig
async def tool_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict:
    session_id = config.get("configurable", {}).get("thread_id", "")
    ...
```

**Warning signs:** `KeyError: 'thread_id'` or empty namespace in store queries; memories are written to `("memories", "")` instead of the correct session namespace.

### Pitfall 4: Setup() CONCURRENTLY Index Creation with autocommit=True

**What goes wrong:** `AsyncPostgresStore.setup()` migration 1 creates a `CONCURRENTLY` index. PostgreSQL requires `CONCURRENTLY` index creation to run OUTSIDE a transaction. With `autocommit=False`, psycopg3 wraps statements in an implicit transaction → `ERROR: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`.

**How to avoid:** Our pool has `autocommit=True`, which means no implicit transaction. CONCURRENTLY index creation works correctly. Do NOT change `autocommit` to `False`.

**Warning signs:** `psycopg.errors.ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block` during `setup()` on first deploy.

### Pitfall 5: `api/requirements.txt` Still on Pre-Upgrade Versions

**What goes wrong:** Vercel's Python function builds from `api/requirements.txt`, which still has `langgraph==0.2.45` and `langchain-core==0.3.63`. Importing `AsyncPostgresSaver` from `langgraph.checkpoint.postgres.aio` fails — that path didn't exist in 0.2.x. Production returns 500 on every memory-enabled request.

**How to avoid:** The first task of Wave 1 must be updating `api/requirements.txt` to match `backend/requirements.txt` minimum-version constraints.

**Warning signs:** Vercel build logs show successful build (pip install succeeds because the old langgraph exists), but runtime 500s with `ImportError: cannot import name 'AsyncPostgresSaver'`.

### Pitfall 6: async tool_node Wiring

**What goes wrong:** Current `tool_node` is a synchronous function. Memory operations (`store.asearch`, `store.aput`, `store.adelete`) are async. Calling `asyncio.run()` inside an already-running event loop crashes.

**How to avoid:** Change `tool_node` to `async def tool_node(...)` and `await` the store operations. LangGraph supports async node functions natively and will call them correctly via `ainvoke`/`astream`.

**Warning signs:** `RuntimeError: This event loop is already running.`

### Pitfall 7: Duplicate Session IDs from Multiple Tabs

**What goes wrong:** If the user opens two browser tabs and both generate a new session_id before writing to localStorage, they get different session_ids. Memory and history are split across two threads.

**How to avoid:** The session_id should be read-and-write-atomically from localStorage at app init. The pattern `getOrCreateSessionId()` (read → if absent → write → return) is safe for same-browser-same-origin because localStorage operations are synchronous.

**Warning signs:** User reports that memories shared in one tab aren't recalled in another open tab. (This is a UX concern, not a correctness bug — each tab has its own session, which may be acceptable for the portfolio demo.)

---

## Code Examples

### AsyncConnectionPool Construction (Supavisor-safe)

```python
# Source: Verified against psycopg3 3.3.4 docs + Supabase troubleshooting guide
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

pool = AsyncConnectionPool(
    conninfo="postgresql://postgres.REF:PASS@aws-0-REGION.pooler.supabase.com:6543/postgres",
    min_size=1,
    max_size=3,
    kwargs={
        "prepare_threshold": None,   # Supabase official recommendation for psycopg3 transaction mode
        "autocommit": True,           # Required by AsyncPostgresSaver/AsyncPostgresStore
        "row_factory": dict_row,      # Required by AsyncPostgresSaver/AsyncPostgresStore
    },
    open=False,
)
await pool.open()
```

### What AsyncPostgresSaver.setup() Creates

```sql
-- Source: Verified against BasePostgresSaver.MIGRATIONS (10 migrations total)
CREATE TABLE IF NOT EXISTS checkpoint_migrations (v INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL, version TEXT NOT NULL,
    type TEXT NOT NULL, blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL, task_id TEXT NOT NULL, idx INTEGER NOT NULL,
    channel TEXT NOT NULL, type TEXT, blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
-- Plus ALTER TABLE, INDEX CONCURRENTLY migrations (migrations 4-9)
```

### What AsyncPostgresStore.setup() Creates

```sql
-- Source: Verified against BasePostgresStore.MIGRATIONS (4 migrations)
CREATE TABLE IF NOT EXISTS store (
    prefix TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    ttl_minutes INT,
    PRIMARY KEY (prefix, key)
);
CREATE TABLE IF NOT EXISTS store_migrations (v INTEGER PRIMARY KEY);
CREATE INDEX CONCURRENTLY IF NOT EXISTS store_prefix_idx ON store
    USING btree (prefix text_pattern_ops);   -- for LIKE prefix queries
CREATE INDEX IF NOT EXISTS idx_store_expires_at ON store (expires_at)
    WHERE expires_at IS NOT NULL;            -- for TTL sweeping
```

### Graph Compilation with Memory

```python
# Source: Verified against StateGraph.compile() signature (langgraph 1.2.6)
graph = build_graph(
    checkpointer=app.state.checkpointer,
    store=app.state.store,
    tracker=tracker,
)
# Invoke with thread_id config:
config = {"configurable": {"thread_id": session_id}}
# Non-streaming:
final_state = await graph.ainvoke(initial_state, config=config)
# Streaming:
async for state in graph.astream(initial_state, config=config, stream_mode="values"):
    ...
```

### Store Namespace Design

```python
# Source: Verified against AsyncPostgresStore._namespace_to_text source
# Namespace tuple ("memories", session_id) stored as "memories.{session_id}" in DB

namespace = ("memories", session_id)            # e.g., ("memories", "7f3a-abc...") 
# -> stored as: prefix = "memories.7f3a-abc..."

# Search (recency-ordered, no vector):
items = await store.asearch(namespace, limit=20)   # ORDER BY updated_at DESC

# Write:
await store.aput(namespace, str(uuid.uuid4()), {"text": "User is based in Sao Paulo"})

# Delete:
await store.adelete(namespace, key)

# Bulk delete for clear-memory:
# raw SQL: DELETE FROM store WHERE prefix LIKE 'memories.{session_id}%'
```

### Thread Deletion (Clear Memory — Checkpoint Side)

```python
# Source: Verified against AsyncPostgresSaver.adelete_thread() source
# Deletes rows from: checkpoints, checkpoint_blobs, checkpoint_writes
await checkpointer.adelete_thread(session_id)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| langgraph 0.2.x — no built-in Store | `langgraph.store.postgres.AsyncPostgresStore` integrated | langgraph 1.0 (2026) | Long-term memory is first-class; no custom table needed |
| `from_conn_string` documented as the standard pattern | Direct constructor with pool recommended for Supavisor | Discovered via GitHub issues 2024-2026 | `from_conn_string` works for direct Postgres; breaks on transaction poolers |
| `supports_pipeline` based on libpq version only | Manually override to `False` for pooler compatibility | GitHub issue #2407 documented this need | Required for Supabase reliability |
| `InMemoryStore` for demos | `AsyncPostgresStore` for production | langgraph 1.0 | Backed by Supabase; survives cold starts |
| Thread_id passed as positional arg | `config={"configurable":{"thread_id":...}}` | Stable across langgraph versions | Same API from 0.2.x to 1.2.x |

**Deprecated/outdated:**
- `langgraph.checkpoint.postgres.PostgresSaver` (sync) — use `AsyncPostgresSaver` for FastAPI
- `InMemoryCheckpointer` — not persistent; use only for tests
- `from_conn_string` context manager — use constructor directly to control connection settings

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `supports_pipeline=False` is a stable public attribute that can be set after construction | Patterns 2, Pitfall 2 | Low: attribute is non-private (no underscore), set in `__init__`; unlikely to change to a property with enforcement |
| A2 | Async `tool_node` is compatible with the existing `graph.stream(stream_mode="values")` call in `api.py` | Pattern 6, Pitfall 6 | Low: LangGraph natively supports async nodes; `astream` is the expected path for async graphs |
| A3 | `api/requirements.txt` does not have Vercel-specific version constraints that would conflict with the upgrade | Pitfall 5 | Low: the file is hand-maintained and previously had only 8 entries; no evidence of version conflicts |
| A4 | Pipeline mode fails on Supabase Supavisor transaction pooler in some versions | Pitfall 2 | Medium: empirically reported in GitHub issues 5675, 2407; Supabase may have fixed this in recent Supavisor versions. Setting `supports_pipeline=False` is the conservative safe path. |
| A5 | The `store` table's prefix column supports LIKE prefix queries efficiently with the installed `store_prefix_idx` (btree + text_pattern_ops) | Pattern 8 | Low: `text_pattern_ops` is specifically designed for LIKE prefix queries; confirmed in store migration SQL |
| A6 | `config` (RunnableConfig) injection via `config: RunnableConfig` parameter in `tool_node` works and contains `thread_id` | Pattern 6 | Low: KWARGS_CONFIG_KEYS shows `config` is in the injection list; `thread_id` is set in all `graph.invoke/astream` calls |
| A7 | Calling `create_pool()` in FastAPI lifespan works correctly in Vercel serverless (lifespan is called on each cold start) | Pattern 3 | Medium: Vercel cold starts do invoke the ASGI lifespan; but if a Lambda is reused and the pool connection goes stale, reconnection depends on psycopg_pool's reconnect behavior |

---

## Open Questions

1. **Does pipeline mode actually fail on the project's specific Supabase region/Supavisor version?**
   - What we know: GitHub issues document failures; Supabase has been updating Supavisor
   - What's unclear: Whether the 2026 Supavisor version on this project's region supports psycopg3 pipeline mode
   - Recommendation: Implement with `supports_pipeline=False` for safety. After deploying, do a quick test with `supports_pipeline=True` on a dev branch to see if it works. If it does, the restriction can be lifted.

2. **Should memory_read be called automatically at the start of every agent turn, or only when the LLM decides to call it?**
   - What we know: The LLM decides when to call tools based on TOOL_SCHEMAS descriptions
   - What's unclear: Whether a directive description will reliably trigger `memory_read` at conversation start
   - Recommendation: Add "Call memory_read at the start of every conversation to check for relevant past context" to the system prompt AND to the `memory_read` tool description. This steers the model to call it reliably while keeping it visible in the trace (MEM-04).

3. **What is the right value for MAX_MEMORIES_STORED (MEM-07)?**
   - What we know: Must be bounded; too many memories hurt LLM context window
   - What's unclear: Optimal N for the portfolio demo use case
   - Recommendation: 20 as default (max ~2-4 KB of memory text in the observation). Make it configurable via env var `MEMORY_MAX_STORED`.

4. **Should setup() run at cold start (lifespan) or only once as a migration?**
   - What we know: setup() is idempotent; runs a few SQL checks per call
   - What's unclear: Cost of running setup() on every Vercel cold start (likely <100ms)
   - Recommendation: Run at lifespan startup. The cost is negligible and ensures tables exist after Supabase project resumes from inactivity pause.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `langgraph-checkpoint-postgres` | MEM-02 (AsyncPostgresSaver) | YES (backend) / NO (api/) | 3.1.0 | Fix api/requirements.txt first |
| `psycopg-pool` | AsyncConnectionPool | YES (backend) / NO (api/) | 3.3.1 | Fix api/requirements.txt first |
| `langgraph.store.postgres` | MEM-03 (AsyncPostgresStore) | YES (backend) / NO (api/) | part of langgraph 1.2.6 | Fix api/requirements.txt first |
| `SUPABASE_POOLER_URL` | Pool creation | YES (Vercel + local .env) | — | Phase blocks without it |
| Supabase checkpoints/store tables | MEM-02, MEM-03 | NO — created by `setup()` | — | setup() call in lifespan |
| `X-Session-Id` header support in CORS | MEM-01 | Check `allow_headers=["*"]` in CORS | — | `["*"]` already allows all headers |

**Missing dependencies with no fallback:**
- `api/requirements.txt` upgrade (blocks ALL Phase 2 Vercel features)

**Missing dependencies with fallback:**
- Checkpoint/store tables (created by `setup()` on first deploy — acceptable)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | None — `python -m unittest discover -s tests -v` |
| Quick run command | `cd backend && python -m unittest discover -s tests -v` |
| Full suite command | Same (all test modules) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEM-01 | X-Session-Id header is read from request and used as thread_id | Unit | `python -m unittest tests.test_api.MemorySessionTests.test_session_id_from_header -v` | NO — Wave 0 gap |
| MEM-02 | Conversation history restores on new request with same session_id | Integration (mocked checkpointer) | `python -m unittest tests.test_memory.CheckpointRestoreTests -v` | NO — Wave 0 gap |
| MEM-03 | Agent references past facts in responses | Integration (mocked store) | `python -m unittest tests.test_memory.LongTermMemoryTests -v` | NO — Wave 0 gap |
| MEM-04 | memory_read/memory_write appear in intermediate_steps | Unit | `python -m unittest tests.test_agent.MemoryToolStepTests -v` | NO — Wave 0 gap |
| MEM-05 | Session ID is returned in API response or accessible in UI state | Unit (frontend) | Manual verify — no frontend test framework | — |
| MEM-06 | Clear memory deletes checkpoint rows and store rows | Integration (mocked DB) | `python -m unittest tests.test_api.ClearMemoryTests -v` | NO — Wave 0 gap |
| MEM-07 | Store entries capped at MAX_MEMORIES_STORED after writes | Unit | `python -m unittest tests.test_memory.MemoryCapTests -v` | NO — Wave 0 gap |

### Success Criteria Verification

| Criterion | How to Verify |
|-----------|--------------|
| SC1: Browser close + return restores history | Open app, type query, close browser, reopen, verify messages visible without re-typing. Requires: session_id in localStorage + checkpointer restore working. |
| SC2: Agent references past facts cross-session | Session A: "My name is Paulo and I work at an AI startup." New session, same session_id: ask "What's my name?" — agent should say "Paulo". |
| SC3: memory_read/memory_write appear as trace Steps | Submit a query that triggers memory; verify SSE stream contains `action=memory_read` or `action=memory_write` events visible in ReasoningPanel. |
| SC4: Session ID visible in UI | Visual inspection: session_id displayed in UI with copy button. Copy → paste into cURL → `GET /api/trace/...` returns correct session data. |
| SC5: Clear memory has no recollection | After "clear memory": submit same query about past facts → agent has no memory. Verify `SELECT COUNT(*) FROM checkpoints WHERE thread_id=?` = 0 in Supabase SQL editor. |

### Observable Integration Test (Cross-Session Persistence Round-Trip)

Manual smoke test for SC1 + SC2 (cannot be fully automated without a real DB):
1. Start backend locally with real `SUPABASE_POOLER_URL`
2. POST `/api/run` with `X-Session-Id: test-session-001`, query = "Remember that my dog is named Rex"
3. Verify `memory_write` Step appears in response `steps`
4. POST `/api/run` with same `X-Session-Id: test-session-001`, query = "What's my dog's name?"
5. Expected: agent responds "Rex" using memory_read step
6. POST `/api/memory/test-session-001` DELETE
7. POST `/api/run` with same session_id, query = "What's my dog's name?"
8. Expected: agent says it has no memory of a dog name

### Sampling Rate

- **Per task commit:** `python -m unittest discover -s tests -v` (existing 58 tests must remain green)
- **Per wave merge:** Full suite + manual cross-session persistence round-trip
- **Phase gate:** All 5 success criteria verifiable via UI before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_memory.py` — new test module for memory operations (mocked store + checkpointer)
- [ ] `backend/tests/test_api.py` additions — session_id extraction, clear_memory endpoint, dual-route registration
- [ ] `SUPABASE_POOLER_URL` in local `.env` (already set from Phase 1 — verify still valid after Supabase resume)
- [ ] Pool construction tested with real Supabase in smoke script before wave 1 implementation

*(If test infrastructure is present: "Existing 58 tests cover regression; new test_memory.py needed for Phase 2 behaviors")*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Partial | Anonymous session_id only; no user auth. session_id is bearer-level identity — attacker who learns it can read that session's memories |
| V3 Session Management | YES | Session ID: UUIDv4 (122 bits entropy), generated client-side via `crypto.randomUUID()`. Not rotatable in MVP. Treat as a semi-secret bearer token. |
| V4 Access Control | YES | Clear memory endpoint must not allow clearing other sessions. Validate: only requests with `X-Session-Id: {session_id}` matching the path param can clear that session. |
| V5 Input Validation | YES | Memory content written to store: validate non-empty, max length (e.g., 500 chars). Namespace injection: session_id used as namespace component — validate it matches UUID format before using in SQL LIKE query. |
| V6 Cryptography | No | No crypto in Phase 2. session_id is not encrypted at rest (Supabase handles DB encryption). |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session ID enumeration / brute-force | Spoofing | UUIDv4 (2^122 space); no sequential IDs. Acceptable for portfolio demo. |
| Memory namespace injection via session_id | Tampering | Validate session_id is a valid UUID format before using in SQL LIKE query: `re.fullmatch(r'^[0-9a-f-]{36}$', session_id)`. Reject malformed IDs with 400. |
| Unbounded memory growth (DoS on free-tier DB) | DoS | MEM-07 top-N cap at write time. Enforce MAX_MEMORIES_STORED (default 20). |
| Cross-session memory access | Elevation of Privilege | Store namespace is namespaced by session_id; SQL queries are parameterized. No cross-session access if session_id is not guessable (UUIDv4). |
| Memory content used for prompt injection | Tampering | Memories are stored as plain text and injected into the system prompt. Add a prompt injection barrier around recalled memories (e.g., "--- BEGIN USER MEMORIES ---\n{memories}\n--- END USER MEMORIES ---"). The existing `python_executor` AST validation is unrelated to this threat. |
| Secret values in stored memories | Information Disclosure | Existing `configure_secure_logging()` redacts secrets from logs. Memory content stored in Supabase is NOT redacted automatically — document this limitation in the README. |
| Stale pool connection after Supabase pause | DoS / Availability | Supabase pauses after 7 days (kept alive by Phase 1 cron). If pool connection stales during Lambda warm period, psycopg_pool handles reconnect. Test reconnect behavior explicitly. |

**CLAUDE.md invariants that Phase 2 must NOT violate:**
- `python_executor` security boundaries unchanged (memory tools do not execute code)
- Global secret redaction (`configure_secure_logging()`) covers `SUPABASE_POOLER_URL` and session IDs must NOT be logged at INFO level (they're semi-secret)
- No LangSmith/external trace backend enabled (`LANGCHAIN_TRACING_V2` must remain unset)
- Every new route registered twice (bare + `/api/` prefix) with vercel.json rewrite for the bare path

---

## Project Constraints (from CLAUDE.md)

These are binding directives from the project's CLAUDE.md files that research findings must not contradict:

1. **No OpenAI/Anthropic dependency.** Memory tools must not add any new LLM provider imports. The existing `FreeModelFallback` (Gemini → Groq → GitHub Models) is the only provider chain.
2. **Every route registered twice** — bare (`/memory/{id}`) and `/api/memory/{id}` — with a vercel.json rewrite entry for the bare path.
3. **Both `backend/requirements.txt` AND `api/requirements.txt` must be updated** when adding new packages. The Phase 1 keepalive deploy failure (500 on production due to missing psycopg in api/requirements.txt) confirmed this invariant. Phase 2 MUST fix api/requirements.txt as the first task.
4. **Secrets are redacted globally** via `configure_secure_logging()`. Do not log session IDs or memory content at INFO/DEBUG level.
5. **`python_executor` security boundary** is unchanged. Memory tools do not execute arbitrary code.
6. **Tool descriptions are directive, not exploratory.** `memory_read` and `memory_write` descriptions must steer the model to call them, not merely offer them as options.
7. **Rate limit: 10/minute per IP** via slowapi. Memory tools are invoked as part of existing `/run` calls — no new rate-limited endpoints needed for the tool invocations themselves. The `DELETE /memory/{session_id}` endpoint should be added to the rate limiter (or explicitly exempt with justification).
8. **`python main.py` is NOT the server.** All server testing uses `python -m uvicorn api:app`.
9. **`@limiter.exempt` must appear ABOVE `@app.*` decorators** (outermost) to avoid FastAPI signature parsing bugs.

---

## Sources

### Primary — Verified Against Installed Source Code (MEDIUM confidence)

- `AsyncPostgresSaver.__init__`, `from_conn_string`, `setup()`, `_cursor()`, `aput()`, `adelete_thread()` — directly inspected source from langgraph-checkpoint-postgres 3.1.0 install [VERIFIED: pip freeze]
- `AsyncPostgresStore.__init__`, `from_conn_string`, `setup()`, `_cursor()`, `asearch()`, `aput()`, `adelete()`, `_prepare_batch_search_queries()` — directly inspected source from langgraph 1.2.6 [VERIFIED: pip freeze]
- `StateGraph.compile()` signature — inspected `langgraph.graph.state.StateGraph.compile` [VERIFIED: pip freeze]
- `KWARGS_CONFIG_KEYS` — inspected `langgraph._internal._runnable` for `store: BaseStore` and `config: RunnableConfig` injection [VERIFIED: pip inspect]
- `_namespace_to_text()` — dot-join of namespace tuple; verified format [VERIFIED: pip inspect]
- `Capabilities().has_pipeline()` — returns True on libpq >= 14; confirmed True in this environment [VERIFIED: pip inspect]
- `BasePostgresSaver.MIGRATIONS` — SQL for 10 checkpoint table migrations [VERIFIED: pip inspect]
- `BasePostgresStore.MIGRATIONS` — SQL for 4 store table migrations [VERIFIED: pip inspect]

### Secondary — Official Documentation (MEDIUM confidence)

- [supabase.com/docs/guides/troubleshooting/disabling-prepared-statements] — `prepare_threshold=None` explicitly recommended for psycopg3 with Supabase transaction pooler [CITED]
- [supabase.com/docs/guides/troubleshooting/supavisor-faq] — transaction mode does not support prepared statements [CITED]
- [docs.langchain.com/oss/python/langgraph/add-memory] — checkpointer + store pattern, thread_id config key [CITED]

### Tertiary — Community / GitHub Issues (LOW confidence)

- [github.com/langchain-ai/langgraph/issues/5675] — AsyncPostgresSaver pipeline mode failures with Supabase SSL [CITED]
- [github.com/langchain-ai/langgraph/issues/2407] — hardcoded pipeline=True issue; fallback path now exists [CITED]
- [medium.com/@termtrix/...] — FastAPI lifespan + pool pattern for LangGraph + Postgres [LOW: community source]

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Checkpointer API (setup, adelete_thread, supports_pipeline) | MEDIUM | Verified against installed source; interface is internal (no public stable contract) |
| Store API (aput, asearch, adelete, namespace format) | MEDIUM | Verified against installed source; store is a newer API, less battle-tested |
| Supabase pooler + prepare_threshold=None | MEDIUM | Official Supabase doc + psycopg confirmed; not smoke-tested yet in this codebase |
| Pipeline mode Supavisor risk | LOW | Empirical reports in GitHub issues; exact behavior depends on Supavisor version |
| api/requirements.txt upgrade path | HIGH | Phase 1 lesson explicitly confirms Vercel deploys from this file |
| Memory-as-tools architecture | MEDIUM | Verified injection mechanism; async tool_node pattern is a codebase change |
| Frontend session_id | HIGH | localStorage + crypto.randomUUID() is standard web practice |

**Research date:** 2026-06-29
**Valid until:** 2026-07-30 (30 days — LangGraph store API is newer and may evolve; verify before implementation if > 2 weeks elapse)
