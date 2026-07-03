# Phase 5: MCP - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 9 (2 new modules, 4 modified, 2 requirements files, 1 test file new + 1 test file extended)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/agent/mcp_server.py` (NEW) | service/tool-provider | request-response | `backend/agent/tools.py` (`web_search`) | role-match |
| `backend/agent/mcp_client.py` (NEW) | service (discovery) | request-response, degrade-to-empty | `backend/api.py` lifespan `pool is None` degrade block | role-match |
| `backend/api.py` (EDIT: mount + lifespan) | config/route wiring | request-response | itself — existing `lifespan`, dual route registration | exact |
| `backend/agent/graph.py` (EDIT: `tool_node`, `TOOL_SCHEMAS`, `build_graph`) | controller (agent loop) | event-driven (tool dispatch) | itself — existing `tool_node`/`_run_document_search`/`pool` threading | exact |
| `vercel.json` (EDIT: add `/mcp/:path*` rewrite) | config | — | itself — existing `rewrites` entries (`/memory/:path*`, `/documents/:path*`) | exact |
| `backend/requirements.txt` / `api/requirements.txt` (EDIT) | config | — | itself — existing pinned-dependency lines | exact |
| `backend/tests/test_mcp.py` (NEW) | test | request-response / unit | `backend/tests/test_memory.py` (`FakeStore` fixture style) | exact |
| `backend/tests/test_graph.py::McpToolNodeTests` (EDIT) | test | unit | `backend/tests/test_graph.py::StepTimingTests` | exact |
| `README.md` (EDIT: new MCP section) | docs | — | existing README "Diagram"/architecture sections (not read in this pass — follow existing heading + mermaid style) | role-match |

## Pattern Assignments

### `backend/agent/mcp_server.py` (NEW — service/tool-provider)

**Analog:** `backend/agent/tools.py` (`web_search`, lines 205-245) for the "real, capped, error-string-not-raise" tool convention; official `mcp` SDK example for the mounting mechanics (already embedded in RESEARCH.md Code Examples, verified against installed source).

**Env-var + cap pattern to copy** (`backend/agent/tools.py:16-18, 190-196, 220-227`):
```python
DEFAULT_TAVILY_MAX_RESULTS = 2
DEFAULT_TAVILY_SNIPPET_CHARS = 360

def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)

# usage inside the tool:
max_results = _env_int("TAVILY_MAX_RESULTS", DEFAULT_TAVILY_MAX_RESULTS, 1, 5)
snippet_chars = _env_int("TAVILY_SNIPPET_CHARS", DEFAULT_TAVILY_SNIPPET_CHARS, 80, 1200)
```
Apply the same shape for `MAX_FETCH_BYTES` / `MAX_RETURNED_CHARS` in `fetch_url` (RESEARCH.md already proposes literal constants; promoting them through `_env_int`-style helpers is optional but matches the existing convention for `web_search`/`python_executor` timeouts).

**Error-string-not-raise pattern** (`backend/agent/tools.py:229-234`):
```python
try:
    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=max_results)
    results = response.get("results", [])[:max_results]
except Exception as exc:
    return f"Error: Tavily search failed: {exc}"
```
`fetch_url` must follow this exact shape: catch broadly, return `f"Error: ..."`, never raise — this is what lets `tool_node`'s existing dispatch (which does not special-case MCP tools for error handling) work unchanged.

**Tool docstring/description convention** (`backend/agent/tools.py:205-216`):
```python
@tool
def web_search(query: str) -> str:
    """Search the web with the Tavily API and return compact results.

    Args:
        query: Search query to send to Tavily.

    Returns:
        A numbered list containing compact results. ...
    """
```
Mirror this docstring shape for `@mcp_server.tool() def fetch_url(url: str) -> str:` — MCP's `FastMCP` derives the tool's exposed schema from the function signature + docstring, so precise argument/return documentation matters more here than for the native `@tool` decorator.

**Mounting mechanics (already verified against installed source in RESEARCH.md; reproduced here as canonical excerpt to copy verbatim):**
```python
mcp_server = FastMCP("react-agent-tools", stateless_http=True, json_response=True)
mcp_server.settings.streamable_http_path = "/"  # avoid /mcp/mcp double-nesting
```

---

### `backend/agent/mcp_client.py` (NEW — service/discovery)

**Analog:** `backend/api.py` lifespan `pool is None` degrade block (lines 132-156) — the exact "try external I/O once at startup, degrade to a safe empty/None value on any failure, never crash app startup" pattern this phase must replicate for MCP discovery.

**Degrade-on-failure pattern to copy** (`backend/api.py:132-152`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from agent.db import create_pool
        ...
        pool = await create_pool()
        await pool.open()
        ...
        app.state.pool = pool
        app.state.checkpointer = checkpointer
        app.state.store = store
    except Exception:
        logger.warning("DB unavailable — memory features degraded (pool/checkpointer/store=None)")
        app.state.pool = None
        app.state.checkpointer = None
        app.state.store = None
    yield
    _pool = getattr(app.state, "pool", None)
    if _pool is not None:
        await _pool.close()
```
`discover_mcp_tools()` must follow the identical shape: a `try/except Exception` around the network call, logging a warning (not re-raising), falling back to `([], [])`, gated first by a plain `if not url: return [], []` check (mirrors the "unset env var = zero I/O" branch already used implicitly for `TAVILY_API_KEY` in `web_search`, `backend/agent/tools.py:220-222`).

**Env-var gate convention to copy** (`backend/agent/graph.py:219, 246`):
```python
WEB_SEARCH_GATE_DISABLE_ENV = "REACT_AGENT_DISABLE_WEB_SEARCH_GATE"
...
return os.getenv(WEB_SEARCH_GATE_DISABLE_ENV, "").lower() in {"1", "true", "yes"}
```
For `MCP_FETCH_SERVER_URL`, the check is simpler (presence/non-empty, not a boolean flag) — use `os.getenv("MCP_FETCH_SERVER_URL", "").strip()` and treat empty string as "unset" (same normalization style: `.strip()` / `.lower()` before comparison).

---

### `backend/api.py` (EDIT — mount MCP sub-app, extend lifespan)

**Analog:** itself. The existing `lifespan` (lines 132-156) is the direct template for combining the MCP `session_manager.run()` context and the `discover_mcp_tools()` call alongside the existing pool/checkpointer/store setup — as a **separate** `try/except`, per RESEARCH.md Pitfall 4 (an MCP failure must not cascade into a DB failure or vice versa).

**Dual route registration convention** (`backend/api.py:479-482, 525-526, 554-555`):
```python
@app.post("/agent/invoke", response_model=AgentResponse)
@app.post("/api/agent/invoke", response_model=AgentResponse)
@app.post("/run", response_model=AgentResponse)
@app.post("/api/run", response_model=AgentResponse)
...

@app.get("/health")
@app.get("/api/health")
async def health(...):
    return {"status": "ok", "tools": list(TOOLS.keys())}
```
**Not applicable to the MCP mount itself** — `app.mount("/mcp", mcp_server.streamable_http_app())` is a single `Mount()`, not a decorated route pair (RESEARCH.md explicitly calls this out: needs exactly one `vercel.json` rewrite, not two route decorators). BUT `/health` and `/config` (which already use this dual-decorator pattern) must be edited to union in MCP tool names — see Pattern 4 excerpt below.

**`/health`/`/config` merge-in-app.state pattern** (RESEARCH.md Architecture Pattern 4, grounded in `backend/api.py:525-528, 554-565`):
```python
@app.get("/health")
@app.get("/api/health")
async def health(request: Request) -> dict[str, object]:
    mcp_names = list(getattr(request.app.state, "mcp_tools", {}).keys())
    return {"status": "ok", "tools": list(TOOLS.keys()) + mcp_names}
```
Existing `/health`/`/config` already read `request.app.state.pool`/`checkpointer`/`store` via `getattr(request.app.state, "pool", None)` (lines 487-489, 509-511) — use this exact `getattr(..., None)`/`getattr(..., {})` defensive-read style for `app.state.mcp_tools`.

**Rate-limit exempt convention (if MCP mount needs exemption — Open Question 1 in RESEARCH.md)** (`backend/api.py:569-571`):
```python
@limiter.exempt
@app.post("/suggestions", response_model=SuggestionsResponse)
@app.post("/api/suggestions", response_model=SuggestionsResponse)
```
Note the CLAUDE.md-documented footgun: `@limiter.exempt` must sit **above** (outermost of) the route decorator(s) or FastAPI misparses the signature (422 errors). `Mount()` is not a decorated route, so this decorator pattern does not directly apply to `/mcp`; if exemption is needed, it would require a different slowapi mechanism (e.g., per-path exclusion in middleware config) — flag for planner decision, not a copy-paste case.

---

### `backend/agent/graph.py` (EDIT — `tool_node`, `TOOL_SCHEMAS`, `build_graph`)

**Analog:** itself — the existing `pool`/`store` optional-parameter threading and `document_search`/`memory_read` dispatch branches are the exact template for adding `mcp_tools`.

**`tool_node` dispatch branch pattern to extend** (`backend/agent/graph.py:491-534`):
```python
async def tool_node(state: AgentState, store: BaseStore, config: RunnableConfig, pool=None) -> dict[str, Any]:
    messages = state.get("messages", [])
    last_ai = _last_ai_message(messages)
    tool_calls = list(last_ai.tool_calls) if last_ai and last_ai.tool_calls else []

    thought = str(last_ai.content) if last_ai else ""
    session_id = config.get("configurable", {}).get("thread_id", "")
    new_messages: list[BaseMessage] = []
    new_steps: list[Step] = []
    for call in tool_calls:
        action = call.get("name", "")
        action_input = _normalize_tool_input(action, _tool_call_action_input(call))
        _step_started = time.perf_counter()
        if action == MEMORY_READ_TOOL_NAME:
            if store is None:
                observation = "Memory is unavailable in this session."
            else:
                observation = await _run_memory_read(store, session_id, action_input)
        elif action == DOCUMENT_SEARCH_TOOL_NAME:
            if pool is None:
                observation = "Document search is unavailable in this session."
            else:
                observation = await _run_document_search(pool, session_id, action_input)
        else:
            observation = _run_tool(action, action_input)
        _elapsed_ms = round((time.perf_counter() - _step_started) * 1000)
        new_messages.append(ToolMessage(content=observation, tool_call_id=call.get("id", action)))
        new_steps.append({
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "observation": observation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": _elapsed_ms,
        })

    return {
        "messages": new_messages,
        "intermediate_steps": [*state.get("intermediate_steps", []), *new_steps],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
```
Add a new `elif mcp_tools and action in mcp_tools:` branch **before** the final `else: observation = _run_tool(...)` fallback, matching the `document_search`/`memory_read` "unavailable" degrade phrasing when `mcp_tools` is falsy — the `Step` construction block below the branch is untouched (SAME shape for every branch, per RESEARCH.md Pattern 3). Per RESEARCH.md, dispatch must use `call.get("args", {})` (the full raw dict) for `.ainvoke()`, not the flattened `action_input` display string (which remains correct for `Step.action_input` only).

**`_tool_call_action_input` generic fallback (already handles MCP args, zero change needed)** (`backend/agent/graph.py:320-329`):
```python
def _tool_call_action_input(call: dict[str, Any]) -> str:
    """Reduce a tool call's structured args to the single display string the
    trace and UI expect (the expression / code / query)."""
    args = call.get("args", {}) or {}
    key = TOOL_INPUT_KEYS.get(call.get("name", ""))
    if key and key in args:
        return str(args[key])
    if len(args) == 1:
        return str(next(iter(args.values())))
    return str(args)
```

**`build_graph` optional-parameter threading pattern to extend** (`backend/agent/graph.py:554-564`):
```python
def build_graph(llm: Any | None = None, tracker: UsageTracker | None = None, checkpointer=None, store=None, pool=None):
    active_llm = llm or _create_default_llm(tracker)
    if tracker is not None:
        active_llm = UsageTrackingLLM(active_llm, tracker)
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_node", lambda state: agent_node(state, active_llm))  # type: ignore

    async def _tool_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict[str, Any]:
        return await tool_node(state, store, config, pool=pool)

    workflow.add_node("tool_node", _tool_node)
```
Add `mcp_tools=None` as a new optional `build_graph` param, close over it in the inner `_tool_node` closure exactly like `pool` is closed over today, and merge into `TOOL_SCHEMAS` for `agent_node`'s `llm.invoke(prompt_messages, tools=TOOL_SCHEMAS)` call (line 365) — pass `TOOL_SCHEMAS + (mcp_schemas or [])`.

**Collision guard (new, no existing analog — write fresh, one-liner):**
```python
mcp_tools = {t.name: t for t in tools if t.name not in TOOLS}
```

---

### `vercel.json` (EDIT — add one rewrite)

**Analog:** itself — existing bare-path rewrite entries.

**Pattern to copy** (`vercel.json:42-44`):
```json
{ "source": "/memory/:path*", "destination": "/api/index.py" },
{ "source": "/upload", "destination": "/api/index.py" },
{ "source": "/documents/:path*", "destination": "/api/index.py" },
```
Add: `{ "source": "/mcp/:path*", "destination": "/api/index.py" }` in the same array, same style (wildcard suffix `:path*` for a mounted sub-app, matching `/memory/:path*` and `/documents/:path*` which are also FastAPI routers/sub-resources rather than single bare paths).

---

### `backend/requirements.txt` / `api/requirements.txt` (EDIT)

**Analog:** itself — both files, current pin format.

`backend/requirements.txt` uses version pins mixing `==` (exact) and `>=` (floor) styles, e.g.:
```
fastapi==0.115.4
langchain-core>=1.4.8
langgraph-checkpoint-postgres>=3.1.0
psycopg[binary]>=3.2.0
```
`api/requirements.txt` mirrors the same dependency set (Vercel deploys from **this** file — MEMORY.md `vercel-requirements-drift` note, already bit this project once). Add to **both** files:
```
langchain-mcp-adapters>=0.3.0,<0.4.0
mcp>=1.28.0,<2.0.0
```
using the double-bounded `>=,<` style RESEARCH.md recommends (no exact existing precedent for a double-bounded pin in this repo — closest analog is the `psycopg[binary]>=3.2.0` floor-only style; the tighter `<` ceiling is a deliberate new addition per RESEARCH.md Pitfall 5, not a stylistic deviation to avoid).

Note: `backend/requirements.txt` as read by the Read tool renders as UTF-16-with-spaces (byte-order artifact) — verify actual file encoding with `Bash`/`git diff` before editing, per CLAUDE.md's guidance that `.env`-adjacent config files should be inspected via Bash rather than assumed.

---

### `backend/tests/test_mcp.py` (NEW)

**Analog:** `backend/tests/test_memory.py` (`FakeStore` fixture style, lines 1-65) for the fixture pattern; `backend/tests/test_graph.py` (`StepTimingTests`, full file) for the `tool_node`-focused assertion style.

**Fixture style to copy** (`backend/tests/test_memory.py:16-56`):
```python
class _FakeItem:
    """Minimal store item exposing .key and .value like AsyncPostgresStore items."""
    def __init__(self, key: str, value: dict, order: int) -> None:
        self.key = key
        self.value = value
        self._order = order

class FakeStore:
    """Async in-memory store whose asearch returns items newest-first."""
    def __init__(self) -> None:
        self._data: dict = {}
        self._counter: int = 0

    async def asearch(self, namespace, limit: int = 20, **kwargs):
        ...
```
For MCP: build a `FakeMCPTool` (or use `langchain_core.tools.StructuredTool.from_function` wrapping an async no-op per VALIDATION.md Wave 0 note) exposing `.name` and an async `.ainvoke(args)`, and a stub replacing `MultiServerMCPClient` with `.get_tools()` returning `[FakeMCPTool(...)]` — same "minimal fake mirroring the real interface" philosophy as `FakeStore`.

**Async test-running helper to copy** (`backend/tests/test_memory.py:63-64`):
```python
def run(coro):
    return asyncio.run(coro)
```

**Env-var patching style to copy** (per RESEARCH.md/VALIDATION.md note; the existing web-search-gate tests use `patch.dict(os.environ, ...)` around `REACT_AGENT_DISABLE_WEB_SEARCH_GATE` — same style applies to `MCP_FETCH_SERVER_URL`):
```python
from unittest.mock import patch
with patch.dict(os.environ, {"MCP_FETCH_SERVER_URL": ""}, clear=False):
    ...
```

**`unittest.TestCase` class-per-behavior naming convention** (`backend/tests/test_memory.py:71-72`, `backend/tests/test_graph.py:27`):
```python
class LongTermMemoryTests(unittest.TestCase):
    """MEM-03: Agent can write and then read back a fact."""
    def setUp(self):
        self.store = FakeStore()
        self.session = "test-session-1"
```
Use `DiscoveryGateTests`, `DiscoveryTests`, `ServerMountTests`, `FetchToolTests` as the class names (already specified in VALIDATION.md's test map) with the same docstring-cites-requirement-ID convention.

---

### `backend/tests/test_graph.py::McpToolNodeTests` (EDIT — extend existing file)

**Analog:** `StepTimingTests` in the same file (lines 27-56) — the exact style to replicate for asserting `Step` shape parity.

**Full pattern to copy** (`backend/tests/test_graph.py:1-56`):
```python
import asyncio
import unittest
from langchain_core.messages import AIMessage

def _calculator_call_message(*expressions):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "calculator", "args": {"expression": expr}, "id": f"call-{index}"}
            for index, expr in enumerate(expressions)
        ],
    )

def _state(message):
    return {
        "messages": [message],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }

class StepTimingTests(unittest.TestCase):
    def test_step_has_integer_elapsed_ms(self):
        from agent.graph import tool_node
        config = {"configurable": {"thread_id": "timing-session"}}
        result = asyncio.run(
            tool_node(_state(_calculator_call_message("2 + 2")), None, config)
        )
        step = result["intermediate_steps"][-1]
        self.assertIn("elapsed_ms", step)
        self.assertIsInstance(step["elapsed_ms"], int)
        self.assertGreaterEqual(step["elapsed_ms"], 0)
```
For `McpToolNodeTests`: build an `AIMessage` with a tool call naming a fake MCP tool (same `tool_calls=[{"name": ..., "args": {...}, "id": ...}]` shape), call `tool_node(_state(msg), None, config, mcp_tools={name: fake_tool})`, and assert the resulting `Step` dict has the same 6 keys (`thought`, `action`, `action_input`, `observation`, `timestamp`, `elapsed_ms`) as the native-tool `StepTimingTests` case. For the error-becomes-observation case, make the fake tool's `.ainvoke` raise, and assert `observation.startswith("Error:")` (mirrors `_run_tool`'s `except Exception as exc: return f"Error: {type(exc).__name__}: {exc}"` at `backend/agent/graph.py:481-482`).

## Shared Patterns

### Degrade-to-empty-on-missing/unreachable dependency
**Source:** `backend/api.py:132-156` (`pool is None` lifespan pattern), `backend/agent/tools.py:220-222` (`TAVILY_API_KEY` missing → error string, no crash)
**Apply to:** `mcp_client.py::discover_mcp_tools()`, `tool_node`'s new MCP branch (`mcp_tools` falsy → same "unavailable" phrasing as `document_search`/`memory_read`)

### Error caught, returned as string, never raised
**Source:** `backend/agent/tools.py:229-234` (`web_search`), `backend/agent/graph.py:479-482` (`_run_tool`)
**Apply to:** `fetch_url` in `mcp_server.py`, the new MCP dispatch branch in `tool_node`

### Optional-parameter threading through `build_graph` → closure → `tool_node`
**Source:** `backend/agent/graph.py:554-564` (`pool` param)
**Apply to:** new `mcp_tools`/`mcp_schemas` params on `build_graph`

### Dual bare + `/api/`-prefixed route registration
**Source:** `backend/api.py:479-482, 525-526, 554-555`
**Apply to:** N/A for the `Mount()` itself (single mount, single `vercel.json` rewrite) — but DOES apply to any newly added `@app.get`/`@app.post` decorator (none currently planned beyond the mount + existing `/health`/`/config` edits)

### Untrusted-content delimiter barrier (prompt injection defense)
**Source:** `backend/agent/graph.py:459-464` (`--- BEGIN/END RETRIEVED DOCUMENTS ---`), `backend/agent/prompts.py:32-34`
**Apply to:** `fetch_url`'s returned content, wrapped as `--- BEGIN FETCHED PAGE --- / --- END FETCHED PAGE ---`, plus one new `SYSTEM_PROMPT` bullet (see RESEARCH.md Code Examples "System prompt addition")

### `_env_int` bounded env-var parsing
**Source:** `backend/agent/tools.py:190-196`
**Apply to:** any new numeric caps in `mcp_server.py` (`MAX_FETCH_BYTES`, `MAX_RETURNED_CHARS`) or `mcp_client.py` (discovery timeout), if the planner wants them env-configurable rather than hardcoded constants

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `README.md` MCP section content (not the heading style, which has an analog) | docs | — | Not read in this pass (out of scope for code-pattern extraction); planner/executor should follow the existing README's established diagram/heading conventions directly when writing this section — no code excerpt applicable. |
| Collision-guard filter (`mcp_tools = {t.name: t for t in tools if t.name not in TOOLS}`) | utility | transform | Genuinely new one-liner; no prior "filter dynamic tools against a static registry" pattern exists in this codebase to copy from. |

## Metadata

**Analog search scope:** `backend/api.py`, `api/index.py`, `vercel.json`, `backend/agent/graph.py`, `backend/agent/tools.py`, `backend/tests/test_memory.py`, `backend/tests/test_graph.py`, `backend/requirements.txt`, `api/requirements.txt`
**Files scanned:** 9
**Pattern extraction date:** 2026-07-02
