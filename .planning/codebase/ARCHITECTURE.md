# Architecture

**Analysis Date:** 2026-06-29

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                          │
├─────────────────────┬──────────────────────┬────────────────────────────┤
│  Chat UI            │  Reasoning Panel     │   Portfolio Landing Page   │
│  `ChatWorkspace`    │  `ReasoningPanel`    │   `PortfolioView`          │
│  `ChatPanel`        │  SSE event stream    │   `HeroSection`, etc.      │
│  `AnimatedAIChat`   │  Telemetry strip     │                            │
└─────────┬───────────┴──────────┬───────────┴────────────────────────────┘
          │                      │
          │ (1) POST /api/run    │ (2) Stream SSE events
          │ with history         │
          ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                                │
│  `api.py`: Routes, SSE streaming, trace store (last 100 runs)          │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  LangGraph StateGraph (agent_node ↔ tool_node)                 │  │
│  │  `backend/agent/graph.py`                                       │  │
│  │                                                                 │  │
│  │  ┌──────────────────┐         ┌──────────────────────┐        │  │
│  │  │  agent_node      │◄────────│  should_continue     │        │  │
│  │  │  (LLM call)      │  route  │  (iteration counter) │        │  │
│  │  │  native tools    │─────────┤  check MAX=10        │        │  │
│  │  └──────────────────┘         └──────────────────────┘        │  │
│  │           │                            ▲                      │  │
│  │           │ tool calls                 │ no calls / final     │  │
│  │           ▼                            │                      │  │
│  │  ┌──────────────────────────────────┐  │                      │  │
│  │  │  tool_node (Execute tools)       │  │                      │  │
│  │  │  web_search | python | calc      │──┘                      │  │
│  │  │  Create Step + ToolMessage       │                         │  │
│  │  └──────────────────────────────────┘                         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Trace Store: deque[AgentResponse] (last 100 runs)                     │
└─────────────────────────────────────────────────────────────────────────┘
          │
          │ (3) Tool calls / LLM invocation
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LLM Providers (FreeModelFallback chain with usage tracking)            │
│  Responder (agent): Gemini → Groq → GitHub Models                      │
│  Suggester: Groq → Gemini → GitHub Models                              │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  External Services                                                      │
│  web_search (Tavily API)  python_executor (subprocess)  calculator      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| App Shell | Navigation, layout, resizable panels, tab management, state persistence | `frontend/src/App.tsx` |
| useAgent Hook | SSE client, session persistence, connection state machine, fallback handling | `frontend/src/hooks/useAgent.ts` |
| ChatWorkspace | Two-column layout: chat + reasoning panel container | `frontend/src/components/ChatWorkspace.tsx` |
| ChatPanel | Message list, input box, starter prompts, suggestions rendering | `frontend/src/components/demo/ChatPanel.tsx` |
| ReasoningPanel | Animated timeline of steps (Thought/Action/Observe/Final), telemetry, progress | `frontend/src/components/demo/ReasoningPanel.tsx` |
| PortfolioView | Landing page: hero, how it works, stack, footer | `frontend/src/components/PortfolioView.tsx` |
| FastAPI Routes | HTTP endpoints for /run, /config, /suggestions, /evals, /trace, SSE setup | `backend/api.py` |
| agent_node | LLM invocation with system prompt, tool schemas, web search guardrail | `backend/agent/graph.py` |
| tool_node | Tool execution, Step creation, ToolMessage generation | `backend/agent/graph.py` |
| should_continue | Route decision: tool_node vs. final_answer vs. error | `backend/agent/graph.py` |
| FreeModelFallback | Provider fallback chain, usage tracking, token counting | `backend/agent/llms.py` |
| Tools | web_search (Tavily), python_executor (subprocess), calculator | `backend/agent/tools.py` |
| Suggestions | Conversation-aware prompt suggester (Groq-preferred) | `backend/agent/suggestions.py` |
| Redaction | Secret scrubbing from logs and exceptions | `backend/agent/redaction.py` |

## Pattern Overview

**Overall:** ReAct Agent (Reasoning + Acting) with LangGraph state management, SSE streaming, and visible reasoning trace.

**Key Characteristics:**
- **Explicit control flow:** LangGraph makes state transitions and routing decisions visible (not implicit)
- **Native tool calling:** No text parsing—OpenAI-compatible function calling across all providers
- **Real-time streaming:** SSE sends each Thought, Action, Observation step to frontend as it happens
- **Free/freemium only:** Multi-provider fallback (Gemini → Groq → GitHub Models) with per-role preferences
- **Security boundaries:** Subprocess isolation for python_executor, AST validation, secret redaction
- **Trace-centric UI:** Reasoning is the primary differentiator, not an afterthought

## Layers

**Frontend (React + Vite):**
- Purpose: Interactive chat UI with resizable panels, real-time reasoning visualization, session persistence
- Location: `frontend/src`
- Contains: Component tree (App → ChatWorkspace/PortfolioView → ChatPanel/ReasoningPanel), hooks (useAgent), types
- Depends on: `/api` endpoints for chat, config, suggestions, evals
- Used by: Browser (Vite dev / production build)

**FastAPI HTTP Layer:**
- Purpose: HTTP endpoints, SSE streaming, rate limiting, CORS, static frontend serving
- Location: `backend/api.py`
- Contains: Routes (POST /run, GET /config, POST /suggestions, etc.), response models, stream handlers
- Depends on: LangGraph agent (build_graph), tool registry, suggestion engine
- Used by: Frontend via fetch/EventSource, `/api/index.py` (Vercel entrypoint)

**LangGraph StateGraph (Agent Logic):**
- Purpose: Explicit 2-node ReAct loop: agent_node invokes LLM, tool_node executes tools
- Location: `backend/agent/graph.py`
- Contains: agent_node, tool_node, should_continue router, state updates, web search guardrail
- Depends on: LLM (FreeModelFallback), tools, state schema (AgentState), SYSTEM_PROMPT
- Used by: FastAPI routes via build_graph()

**Tool Layer:**
- Purpose: Execute web searches, run sandboxed Python, evaluate math expressions
- Location: `backend/agent/tools.py`
- Contains: web_search (Tavily), python_executor (subprocess with AST/import whitelist), calculator
- Depends on: External APIs (Tavily), local subprocess, math module
- Used by: tool_node for each tool call

**LLM Provider Layer:**
- Purpose: Multi-provider fallback with per-role preference and usage tracking
- Location: `backend/agent/llms.py`
- Contains: FreeModelFallback, UsageTracker, responder_provider, suggester_provider functions
- Depends on: External LLM APIs (Gemini, Groq, GitHub Models)
- Used by: agent_node (responder), suggestions.py (suggester)

**Suggestion Engine:**
- Purpose: Conversation-aware follow-up prompt generation (non-blocking, degrades to static fallback)
- Location: `backend/agent/suggestions.py`
- Contains: generate_suggestions function, static fallback list
- Depends on: LLM (Groq-preferred), tool registry
- Used by: POST /suggestions endpoint

**Security & Logging:**
- Purpose: Secret redaction from logs, security isolation
- Location: `backend/agent/redaction.py`
- Contains: configure_secure_logging, log record factory monkey-patch
- Depends on: Python logging module
- Used by: Imported at api.py startup

## Data Flow

### Primary Request Path (Chat Query with Streaming)

1. **Frontend sends query** (`frontend/src/hooks/useAgent.ts:sendQuery()`)
   - POST to `/api/run` with `stream: true`, including chat history (last 8 messages)
   - Opens EventSource to consume SSE events

2. **FastAPI receives request** (`backend/api.py:run_agent()`)
   - Parses QueryRequest (query, stream flag, history)
   - Generates run_id, starts timer
   - Calls `_stream_agent()` to return AsyncIterator[SSE payloads]

3. **Initial state construction** (`backend/api.py:_initial_state()`)
   - Converts history messages to LangChain BaseMessage objects (last 8)
   - Appends current query as HumanMessage
   - Initializes AgentState: messages, intermediate_steps=[], iteration_count=0, final_answer=None

4. **LangGraph stream** (`backend/agent/graph.py:agent_node()`)
   - **Step A: Web search guardrail check**
     - If query matches CURRENT_FACT_PATTERNS or EXTERNAL_LOOKUP_PATTERNS AND no tool calls yet
     - Force `_forced_web_search_message()` with web_search tool call (hard cap: 2 searches per run)
   - **Step B: LLM invocation**
     - SystemMessage with SYSTEM_PROMPT + runtime context (current date, current-fact rules)
     - AI Message(s) and ToolMessage(s) from history
     - HumanMessage with current query
     - Calls FreeModelFallback.invoke() with TOOL_SCHEMAS (native function calling)
     - Responder prefers Gemini; falls back Groq → GitHub Models
   - **Step C: Tool call detection**
     - If response.tool_calls is non-empty, route to should_continue → tool_node
     - If response is final_answer, route to should_continue → END
     - If iteration_count ≥ 10, raise MaxIterationsError

5. **Tool execution** (`backend/agent/graph.py:tool_node()`)
   - For each tool call in AIMessage.tool_calls
   - Execute: web_search via Tavily, python_executor via subprocess, calculator via eval
   - Create ToolMessage with observation
   - Create Step dict: {thought, action, action_input, observation, timestamp, elapsed_ms}
   - Increment iteration_count
   - Return updated state with new Step + ToolMessage

6. **SSE emission loop** (`backend/api.py:_stream_agent()`)
   - For each state yielded from graph.stream(), read intermediate_steps
   - For each new Step (tracked by printed_steps counter):
     - Emit "thought" SSE event
     - Emit "action" SSE event with tool name
     - Emit "observation" SSE event
   - After final state or MaxIterationsError:
     - Emit "final" SSE event with result + usage

7. **Frontend receives stream** (`frontend/src/hooks/useAgent.ts`)
   - `parseSseEvents()` buffers and splits SSE chunks by `\n\n`
   - For each JSON payload: update step array, append to messages on "final" event
   - Persist session to localStorage (messages, steps, runSummary)
   - Trigger suggestions fetch after answer renders

8. **Suggestions fetch** (non-blocking, POST /api/suggestions)
   - Frontend sends last few messages + tools_used
   - Suggester invokes Groq-preferred LLM for follow-up prompts (3-5 suggestions)
   - Falls back to static list on any failure
   - Frontend renders suggestions below message

### State Management

**Backend State (LangGraph):**
- Immutable per-iteration, accumulated in `intermediate_steps`
- Messages list grows with each ToolMessage
- iteration_count increments after each tool call
- final_answer set when agent_node returns non-tool response

**Frontend State (useAgent hook):**
- Messages: user + assistant turns (persisted in localStorage)
- Steps: individual Thought/Action/Observation events from SSE stream
- runSummary: run_id, elapsed_ms, tools_used, status, usage
- connectionStatus: 'checking' → 'online'/'mock'/'error'
- Suggestions: array of follow-up prompts

**Session Persistence:**
- localStorage key: `react-agent:chat-session:v1`
- Stores: messages[], steps[], runSummary
- Survives page reload, tab close/reopen

## Key Abstractions

**AgentState (TypedDict):**
- Purpose: LangGraph state schema—passed between nodes, immutable per iteration
- Examples: `backend/agent/state.py`
- Pattern: Annotated list[BaseMessage] with operator.add for message accumulation

**Step (TypedDict):**
- Purpose: Single Thought/Action/Observation event in the trace
- Fields: thought, action, action_input, observation, timestamp, elapsed_ms, run_id, status
- Pattern: Created in tool_node, emitted as SSE, stored in AgentResponse

**FreeModelFallback (LLM):**
- Purpose: Transparent multi-provider fallback with usage tracking
- Pattern: Tries Gemini → Groq → GitHub Models; if one fails, skips to next; raises RuntimeError if all fail
- Usage tracking: Each LLM call recorded, aggregated in UsageTracker

**TOOL_SCHEMAS:**
- Purpose: OpenAI-compatible function schemas that steer model toward tool use
- Pattern: Descriptions are deliberately directive ("Use this instead of computing it yourself")
- Updated dynamically: Not hardcoded per-tool behavior

**Web Search Guardrail:**
- Purpose: Force web_search before allowing direct answer to current-fact questions
- Pattern: Regex match on query against CURRENT_FACT_PATTERNS or EXTERNAL_LOOKUP_PATTERNS
- Hard cap: MAX_CURRENT_FACT_WEB_SEARCHES = 2 to prevent search loops

## Entry Points

**Browser (Frontend):**
- Location: `frontend/src/main.tsx` → `App.tsx`
- Triggers: User opens app in browser, Vite dev server or production build
- Responsibilities: Render shell, initialize useAgent hook, handle navigation

**FastAPI Server:**
- Location: `backend/api.py`
- Triggers: `python -m uvicorn api:app --reload --port 8000` (local dev)
- Responsibilities: HTTP routing, SSE streaming, trace storage, rate limiting

**Vercel Entrypoint:**
- Location: `api/index.py`
- Triggers: Vercel receives request, routes to Python Function
- Responsibilities: Load backend/api.py dynamically via importlib, re-export app

**LangGraph Invocation:**
- Location: `backend/api.py:run_agent()` or `_stream_agent()`
- Triggers: POST /api/run or /api/agent/invoke
- Responsibilities: Call `build_graph()`, invoke or stream over graph

## Architectural Constraints

- **Threading:** Single-threaded event loop (async/await). Tool node runs tools sequentially within the graph.
- **Global state:** 
  - `RUNS` dict: in-memory trace store (last 100 runs), keyed by run_id
  - `RUN_ORDER` deque: FIFO eviction when max stored runs exceeded
  - LLM model environment loaded once at startup (env vars cached)
- **Circular imports:** None; layer dependencies are acyclic (frontend → FastAPI → agent → tools/llms/suggestions)
- **Native tool calling only:** All providers reached through OpenAI-compatible path; no text parsing ReAct
- **Max iterations hard boundary:** `should_continue` raises `MaxIterationsError` at 10 iterations, not silent break
- **Session persistence:** Frontend-only (localStorage); backend has no session concept, only run traces
- **Rate limiting:** 10 req/min per IP via slowapi; `/suggestions` exempt (already rate-limited by turn cost)
- **Web search gating:** Two patterns (CURRENT_FACT_PATTERNS + EXTERNAL_LOOKUP_PATTERNS) trigger forced web_search; cap of 2 per run prevents loops
- **History window:** Only last 8 messages sent to LLM; full session kept in localStorage
- **Tool whitelist:** python_executor allows only specific imports (math, json, re, statistics, random, itertools, functools, sympy, numpy)

## Anti-Patterns

### Text Parsing ReAct

**What happens:** Model reasoning is parsed from text (e.g., "Thought:" / "Action:" line matching)
**Why it's wrong:** Fragile to model phrasing variations; non-deterministic; no way to validate intermediate steps
**Do this instead:** Use native tool calling (OpenAI-compat function_call field in response). All providers in the fallback chain support it. See `agent_node()` which reads response.tool_calls directly.

### Unbounded Agent Loops

**What happens:** Agent can call tools indefinitely with no hard stop
**Why it's wrong:** Runaway reasoning = user waits forever, quota burns, debugging becomes impossible
**Do this instead:** Set MAX_ITERATIONS = 10 and check iteration_count in should_continue. Raise MaxIterationsError explicitly (not silent break). See `backend/agent/graph.py:should_continue()` at line ~350.

### In-Process Code Execution

**What happens:** `exec()` or `eval()` run in the same process as the API
**Why it's wrong:** Any malicious code breaks containment and can access the entire process memory (API keys, secrets, etc.)
**Do this instead:** Run user code in a subprocess with AST validation, import whitelist, blocked builtins, and timeout. See `backend/agent/tools.py:python_executor` which uses subprocess.run with a 10s timeout, validates AST nodes, and only allows whitelisted imports.

### Unredacted Secrets in Logs

**What happens:** API keys or Bearer tokens appear in log lines and exception messages
**Why it's wrong:** Logs get aggregated to external systems; secrets leak into version control via error reports
**Do this instead:** Use `redaction.py` which monkey-patches the logging record factory at startup. Configure secret values (API keys, tokens) and they are scrubbed from every log line and exception string. See `backend/agent/redaction.py:configure_secure_logging()`.

### Hard-Coded Tool Behavior

**What happens:** Tool list and per-tool rules are scattered across prompts and code
**Why it's wrong:** Adding a new tool requires changes in multiple places; tool schemas and behavior diverge
**Do this instead:** Centralize tool registry in `TOOLS` dict and `TOOL_SCHEMAS` array. Pass tool list to suggestion engine at call time (not hardcoded). See `backend/agent/graph.py` for tool definition, `backend/api.py` for dynamic tool passing to suggestions.

## Error Handling

**Strategy:** Explicit exceptions with context, SSE graceful degradation, static fallbacks for non-critical features.

**Patterns:**
- MaxIterationsError: Raised in should_continue at iteration 10, caught in _stream_agent, emitted as "final" SSE event with status="error"
- Tool execution failure: Exception caught in tool_node, returned as observation string (e.g., "Error: web search failed"), LLM sees it and can retry or adjust
- LLM provider failure: FreeModelFallback tries next provider; if all fail, raises RuntimeError with concatenated redacted errors
- Suggestions failure: Falls back to static list (degrades gracefully, does not block answer)
- Rate limit exceeded: slowapi returns HTTP 429; frontend retries (not automatic, user can try again)
- Invalid tool call: Tool schema validation happens at LLM level (native function calling); malformed calls not invoked
- SSE stream interruption: Frontend detects connection close, shows error state, allows user to retry

## Cross-Cutting Concerns

**Logging:** 
- Configured via `configure_secure_logging()` which installs a FactoryFilter
- All log records automatically have configured secrets scrubbed
- Levels: DEBUG (usefulness), INFO (request/response), WARNING (missing env vars), ERROR (exceptions)

**Validation:**
- QueryRequest pydantic model validates query, stream, history fields
- LangChain message types enforce role/content structure
- Python executor uses AST validation (no eval of arbitrary AST nodes)
- Calculator uses AST validation (only math operators, constants, math.* functions allowed)
- Tool schema validation happens at LLM level (native function calling)

**Authentication:**
- No user authentication (portfolio demo)
- API key authentication is provider-specific (Gemini, Groq, GitHub Models, Tavily)
- Keys loaded from environment variables at startup
- Secrets redacted globally from logs

**Observability:**
- Usage tracking: Token counts, estimated cost, provider used, per-call latency
- Trace storage: Last 100 runs retrievable via GET /trace/{run_id}
- SSE stream: Real-time visibility into agent reasoning
- Evaluation harness: Measures task success + tool selection accuracy against labelled dataset

---

*Architecture analysis: 2026-06-29*
