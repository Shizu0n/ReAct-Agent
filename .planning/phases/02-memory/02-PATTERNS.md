# Phase 2: Memory — Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/agent/db.py` (MODIFY) | utility | request-response | `backend/agent/db.py` itself (existing pooler_connection) | exact |
| `backend/agent/graph.py` (MODIFY) | service | event-driven | `backend/agent/graph.py` itself (tool_node, build_graph, TOOL_SCHEMAS) | exact |
| `backend/api.py` (MODIFY) | controller | request-response | `backend/api.py` itself (keepalive_handler dual-route, run_agent, _stream_agent) | exact |
| `api/requirements.txt` (MODIFY) | config | — | `backend/requirements.txt` (already synced in Phase 1) | exact |
| `frontend/src/hooks/useAgent.ts` (MODIFY) | hook | event-driven | `frontend/src/hooks/useAgent.ts` itself (readPersistedSession, persistSession, runApi fetch) | exact |
| `frontend/src/components/demo/ChatPanel.tsx` (MODIFY) | component | request-response | `frontend/src/components/demo/ChatPanel.tsx` itself (StatusStrip chips, onClearHistory button) | exact |
| `backend/tests/test_memory.py` (NEW) | test | — | `backend/tests/test_agent.py` (ScriptedLLM, make_tool_call, unittest.TestCase structure) | role-match |
| `backend/tests/test_api.py` (MODIFY) | test | — | `backend/tests/test_api.py` itself (FakeGraph, TestClient, patch pattern) | exact |
| `backend/tests/test_agent.py` (MODIFY) | test | — | `backend/tests/test_agent.py` itself (tool_node invocation, step assertion pattern) | exact |

---

## Pattern Assignments

### `backend/agent/db.py` — add `create_pool()` (MODIFY)

**Analog:** `backend/agent/db.py` lines 1–54 (existing `pooler_connection`)

**Existing imports pattern** (lines 1–9):
```python
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg.rows import dict_row
```

**New import to add** (after existing imports):
```python
from psycopg_pool import AsyncConnectionPool
```

**Existing connection factory pattern** (lines 25–39) — the `create_pool` factory must use the SAME settings already proven in `pooler_connection`:
```python
@asynccontextmanager
async def pooler_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    async with await psycopg.AsyncConnection.connect(
        _pooler_url(),
        prepare_threshold=None,   # required: Supavisor transaction mode
        autocommit=True,          # required: AsyncPostgresSaver (Phase 2)
        row_factory=dict_row,     # required: AsyncPostgresSaver (Phase 2)
    ) as conn:
        yield conn
```

**New function to add** — mirrors the per-connection settings as pool `kwargs`:
```python
async def create_pool(min_size: int = 1, max_size: int = 3) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=_pooler_url(),
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "prepare_threshold": None,
            "autocommit": True,
            "row_factory": dict_row,
        },
        open=False,
    )
    return pool
```

**Key invariant:** `_pooler_url()` and `_direct_url()` private helpers already exist at lines 11–20 — reuse `_pooler_url()` in `create_pool`, do not duplicate the env-var read.

---

### `backend/agent/graph.py` — add memory tools + async tool_node + build_graph wiring (MODIFY)

**Analog:** `backend/agent/graph.py` lines 1–401 (entire file — tool dispatch loop is the primary pattern)

**Imports to add** (after existing imports at lines 1–26):
```python
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
```

**TOOL_INPUT_KEYS pattern** (lines 37–41) — add two new entries using the same dict literal style:
```python
TOOL_INPUT_KEYS = {
    WEB_SEARCH_TOOL_NAME: "query",
    PYTHON_EXECUTOR_TOOL_NAME: "code",
    CALCULATOR_TOOL_NAME: "expression",
    # Add:
    MEMORY_READ_TOOL_NAME: "query",
    MEMORY_WRITE_TOOL_NAME: "content",
}
```

**TOOL_SCHEMAS pattern** (lines 46–115) — new entries must copy the same dict structure and use directive descriptions:
```python
{
    "type": "function",
    "function": {
        "name": MEMORY_READ_TOOL_NAME,
        "description": (
            "Read facts the user has shared in previous sessions. Call this at "
            "the start of any conversation where the user refers to a past "
            "interaction or where you want to personalize your response. Returns "
            "stored facts ordered by recency."
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
```

**tool_node dispatch loop pattern** (lines 343–372) — async version must keep the Step dict shape and ToolMessage creation identical; only the function signature and memory branches are new:
```python
# EXISTING synchronous dispatch (lines 343–372):
def tool_node(state: AgentState) -> dict[str, Any]:
    ...
    for call in tool_calls:
        action = call.get("name", "")
        action_input = _normalize_tool_input(action, _tool_call_action_input(call))
        observation = _run_tool(action, action_input)
        new_messages.append(
            ToolMessage(content=observation, tool_call_id=call.get("id", action))
        )
        new_steps.append(
            {
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "observation": observation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    return {
        "messages": new_messages,
        "intermediate_steps": [*state.get("intermediate_steps", []), *new_steps],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
```

New signature (signature only — body structure identical):
```python
async def tool_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict[str, Any]:
    session_id = config.get("configurable", {}).get("thread_id", "")
    # ... same loop; replace _run_tool() call with:
    if action == MEMORY_READ_TOOL_NAME:
        observation = await _run_memory_read(store, session_id, action_input)
    elif action == MEMORY_WRITE_TOOL_NAME:
        observation = await _run_memory_write(store, session_id, action_input)
    else:
        observation = _run_tool(action, action_input)
```

**build_graph pattern** (lines 386–400) — add `checkpointer` and `store` parameters, pass to `compile()`:
```python
# EXISTING (lines 386–400):
def build_graph(llm: Any | None = None, tracker: UsageTracker | None = None):
    ...
    return workflow.compile()

# MODIFIED signature only — body structure unchanged:
def build_graph(llm=None, tracker=None, checkpointer=None, store=None):
    ...
    return workflow.compile(checkpointer=checkpointer, store=store)
```

---

### `backend/api.py` — add lifespan, session_id extraction, DELETE /memory/{session_id} (MODIFY)

**Analog:** `backend/api.py` lines 379–405 (keepalive_handler — dual-route registration + `request.app.state` + DB access pattern)

**Dual-route registration pattern** (lines 379–405):
```python
@app.get("/keepalive")
@app.get("/api/keepalive")
async def keepalive_handler(request: Request):
    from agent.db import pooler_connection
    ...
    async with pooler_connection() as conn:
        await conn.execute(...)
    return {"status": "ok", "pinged_at": now.isoformat()}
```

**New clear_memory endpoint** — copies dual-registration + `request.app.state` access:
```python
@app.delete("/memory/{session_id}")
@app.delete("/api/memory/{session_id}")
async def clear_memory(session_id: str, request: Request) -> dict:
    checkpointer = request.app.state.checkpointer
    store = request.app.state.store
    pool = request.app.state.pool
    await checkpointer.adelete_thread(session_id)
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM store WHERE prefix LIKE %s",
            (f"memories.{session_id}%",),
        )
    return {"status": "cleared", "session_id": session_id}
```

**FastAPI app instantiation pattern** (lines 87–98) — add `lifespan=` parameter:
```python
# EXISTING (line 88):
app = FastAPI(title="01 React Agent API")

# MODIFIED:
app = FastAPI(title="01 React Agent API", lifespan=lifespan)
```

**Lifespan pattern** — follows Python contextlib convention; place BEFORE `app = FastAPI(...)`:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent.db import create_pool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.store.postgres import AsyncPostgresStore

    pool = await create_pool()
    await pool.open()
    checkpointer = AsyncPostgresSaver(conn=pool)
    checkpointer.supports_pipeline = False
    store = AsyncPostgresStore(conn=pool)
    store.supports_pipeline = False
    await checkpointer.setup()
    await store.setup()

    app.state.pool = pool
    app.state.checkpointer = checkpointer
    app.state.store = store
    yield
    await pool.close()
```

**Session ID extraction** — add as module-level helper (same style as `_history_messages` at lines 125–136):
```python
def _get_session_id(request: Request) -> str:
    session_id = request.headers.get("x-session-id", "").strip()
    return session_id if session_id else str(uuid.uuid4())

def _graph_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}
```

**`@limiter.exempt` placement rule** (lines 423–435) — `@limiter.exempt` must be the OUTERMOST decorator:
```python
@limiter.exempt
@app.post("/suggestions", ...)
@app.post("/api/suggestions", ...)
async def suggestions(...):
```
Apply the same ordering if `clear_memory` is exempt, or omit `@limiter.exempt` to use the default 10/min limit.

**run_agent / _stream_agent wiring** — `build_graph` call in `_run_agent` (line 202) and `_stream_agent` (line 261) gains `checkpointer` and `store` from `request.app.state`; `run_agent` handler must accept `request: Request` (already does) and pass session_id to `build_graph` or `graph.invoke`:
```python
# EXISTING _run_agent call site (lines 201-206):
def _run_agent(query, run_id, started_at, history=None):
    tracker = UsageTracker()
    graph = build_graph(tracker=tracker)
    final_state = graph.invoke(_initial_state(query, history))
```

---

### `api/requirements.txt` (MODIFY)

**Analog:** `backend/requirements.txt` (source of truth)

**Current state** (lines 1–9) — stale versions that will break production:
```
langchain-core==0.3.63
langgraph==0.2.45
# Missing: langgraph-checkpoint-postgres, psycopg-pool, langchain, langchain-community, langsmith
```

**Pattern:** Replace entire file with minimum-version constraints matching `backend/requirements.txt`. The Phase 1 lesson (psycopg missing from `api/requirements.txt` caused production 500s) is the governing precedent — both files must stay in sync.

---

### `frontend/src/hooks/useAgent.ts` — add sessionId (MODIFY)

**Analog:** `frontend/src/hooks/useAgent.ts` lines 115–156 (`readPersistedSession` / `persistSession` localStorage pattern)

**localStorage read pattern** (lines 115–136):
```typescript
const sessionStorageKey = 'react-agent:chat-session:v1'

function readPersistedSession(): PersistedAgentSession {
  if (typeof window === 'undefined') {
    return { messages: [], steps: [], runSummary: null }
  }
  try {
    const rawSession = window.localStorage.getItem(sessionStorageKey)
    if (!rawSession) return { messages: [], steps: [], runSummary: null }
    const parsed = JSON.parse(rawSession) as unknown
    ...
  } catch {
    window.localStorage.removeItem(sessionStorageKey)
    return { messages: [], steps: [], runSummary: null }
  }
}
```

**New session ID helper** — follows the same guard + localStorage pattern:
```typescript
const SESSION_ID_KEY = 'react-agent:session-id'

function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return ''
  const existing = window.localStorage.getItem(SESSION_ID_KEY)
  if (existing) return existing
  const id = crypto.randomUUID()
  window.localStorage.setItem(SESSION_ID_KEY, id)
  return id
}
```

**fetch call pattern in `runApi`** (lines 540–545) — add header using the same object style:
```typescript
// EXISTING:
const response = await fetch(`${baseUrl}/run`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, stream: true, history: historyForApi(history) }),
})

// MODIFIED — add one header:
headers: {
  'Content-Type': 'application/json',
  'X-Session-Id': getOrCreateSessionId(),
},
```

**Return value pattern** (line 641):
```typescript
// EXISTING:
return { state, sendQuery, clearHistory }

// MODIFIED:
return { state, sendQuery, clearHistory, sessionId: getOrCreateSessionId() }
```

**clearHistory clear-memory fetch** — follows the same try/catch fetch guard as `fetchSuggestions` (lines 290–312); add a fire-and-forget DELETE before clearing state:
```typescript
// Pattern reference: fetchSuggestions (lines 290-312)
async function fetchSuggestions(...): Promise<string[]> {
  try {
    const response = await fetch(`${apiBaseUrl()}/suggestions`, { method: 'POST', ... })
    if (!response.ok) return fallbackSuggestions
    ...
  } catch {
    return fallbackSuggestions
  }
}
```

---

### `frontend/src/components/demo/ChatPanel.tsx` — add session ID badge + clear memory button (MODIFY)

**Analog:** `frontend/src/components/demo/ChatPanel.tsx` lines 76–115 (`StatusStrip` — chip/badge rendering pattern)

**Badge/chip pattern** (lines 102–113):
```tsx
<span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono">
  <CircuitBoard className="h-3 w-3 text-[var(--accent-text)]" />
  {modelSummary}
</span>
```

**Session ID chip** — copy the chip style, add click-to-copy via `navigator.clipboard.writeText`:
```tsx
<span
  className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono"
  title="Click to copy session ID"
  onClick={() => navigator.clipboard.writeText(sessionId)}
>
  {sessionId.slice(0, 8)}…
</span>
```

**`onClearHistory` prop pattern** (lines 16–23, 64–71) — `onClearHistory` is already threaded through `ChatPanelProps` and `PromptInput`; "Clear Memory" button replaces or extends the existing clear button:
```tsx
type ChatPanelProps = {
  ...
  onClearHistory?: () => void   // already exists
}
```

**`canClearHistory` guard pattern** (line 28):
```typescript
const canClearHistory = state.messages.length > 0 || state.steps.length > 0 || state.runSummary !== null
```
The "Clear Memory" button should use the same guard so it only appears when there is something to clear.

---

### `backend/tests/test_memory.py` (NEW)

**Analog:** `backend/tests/test_agent.py` lines 1–60 (module structure, ScriptedLLM, make_tool_call, TestCase)

**Test module structure pattern** (lines 1–12):
```python
import unittest
import os
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
```

**ScriptedLLM helper** (lines 15–22) — copy verbatim; used in test_agent.py already:
```python
class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages, tools=None):
        response = next(self._responses)
        return response if isinstance(response, AIMessage) else AIMessage(content=response)
```

**TestCase naming pattern**: `<Feature>Tests` suffix (e.g., `CheckpointRestoreTests`, `LongTermMemoryTests`, `MemoryCapTests`).

**Mocking pattern** (lines 2–3 of test_api.py, FakeGraph pattern):
```python
# Fake store for unit tests:
class FakeStore:
    def __init__(self):
        self._data: dict = {}

    async def asearch(self, namespace, limit=20):
        ...
    async def aput(self, namespace, key, value):
        ...
    async def adelete(self, namespace, key):
        ...
```

**Tool call assertion pattern** (test_agent.py — `make_tool_call` helper, lines 8–12):
```python
def make_tool_call(name, call_id="call-1", **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )
```

---

### `backend/tests/test_api.py` — add session_id + clear_memory tests (MODIFY)

**Analog:** `backend/tests/test_api.py` lines 1–80 (FakeGraph, TestClient, patch pattern)

**TestClient + patch pattern** (lines 1–50):
```python
from fastapi.testclient import TestClient
from unittest.mock import patch

# Test uses @patch('agent.graph.build_graph', return_value=FakeGraph()) pattern
```

**FakeGraph stream/invoke pattern** (lines 18–40) — new tests for clear_memory use `TestClient.delete()` with the same client setup; mock `request.app.state.checkpointer` and `request.app.state.store`.

---

### `backend/tests/test_agent.py` — add memory tool step tests (MODIFY)

**Analog:** `backend/tests/test_agent.py` (tool dispatch and Step shape assertions)

**Step shape assertion pattern** — new `MemoryToolStepTests` verifies that `memory_read`/`memory_write` produce Steps with `action`, `action_input`, `observation`, `timestamp` keys (same four keys all existing Steps use):
```python
# EXISTING step dict shape (graph.py lines 358-365):
{
    "thought": thought,
    "action": action,
    "action_input": action_input,
    "observation": observation,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
```
Assert this exact shape is present for memory tool calls.

---

## Shared Patterns

### Dual-Route Registration (every new endpoint)
**Source:** `backend/api.py` lines 355–366, 379–382
**Apply to:** `DELETE /memory/{session_id}`
```python
@app.delete("/memory/{session_id}")
@app.delete("/api/memory/{session_id}")
async def clear_memory(...):
```

### `app.state` for Shared Objects
**Source:** `backend/api.py` keepalive_handler — `request.app.state` access
**Apply to:** `clear_memory`, `run_agent`, `_run_agent`, `_stream_agent`
```python
checkpointer = request.app.state.checkpointer
store = request.app.state.store
pool = request.app.state.pool
```

### Step Dict Shape (all tool observations)
**Source:** `backend/agent/graph.py` lines 358–365
**Apply to:** `_run_memory_read` and `_run_memory_write` — their return value becomes the `observation` field in a Step that must have `thought`, `action`, `action_input`, `observation`, `timestamp`.

### Rate Limiter Decorator Order
**Source:** `backend/api.py` lines 423–435 (`@limiter.exempt` must be outermost)
**Apply to:** Any new endpoint that needs `@limiter.exempt`
```python
@limiter.exempt        # OUTERMOST — must come before @app.*
@app.delete("/memory/{session_id}")
@app.delete("/api/memory/{session_id}")
async def clear_memory(...):
```

### localStorage Guard Pattern
**Source:** `frontend/src/hooks/useAgent.ts` lines 115–120
**Apply to:** `getOrCreateSessionId()`
```typescript
if (typeof window === 'undefined') return <default>
```

### Directive Tool Description Style
**Source:** `backend/agent/graph.py` lines 51–114 (TOOL_SCHEMAS)
**Apply to:** `memory_read` and `memory_write` descriptions — must tell the model to call the tool, not offer it as an option ("Call this at the start of every conversation…", "Call this when the user shares…").

---

## No Analog Found

None. All Phase 2 files have strong analogs within the existing codebase. The patterns are fully established by Phase 1 code.

---

## Metadata

**Analog search scope:** `backend/agent/`, `backend/api.py`, `backend/tests/`, `frontend/src/hooks/`, `frontend/src/components/demo/`
**Files scanned:** 8 source files read directly
**Pattern extraction date:** 2026-06-29
