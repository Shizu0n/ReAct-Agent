# ReAct Agent — Full-Stack

Full-stack ReAct agent: FastAPI + LangGraph backend with visible reasoning trace, React + Vite frontend with live SSE streaming, resizable sidebar panels, and a portfolio landing page. Free/freemium model providers only, zero OpenAI/Anthropic dependency.

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.4-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.45-purple)
![React 19](https://img.shields.io/badge/React-19-61DAFB)
![Vite 8](https://img.shields.io/badge/Vite-8-646CFF)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-06B6D4)
![Vercel](https://img.shields.io/badge/Deploy-Vercel-black)

## Architecture

```text
react-agent/
├── backend/              FastAPI app, LangGraph ReAct agent, tools, tests
│   ├── agent/
│   │   ├── graph.py      StateGraph: agent_node, tool_node, should_continue
│   │   ├── llms.py       FreeModelFallback chain (Gemini → Groq → GitHub → OpenRouter → CF)
│   │   ├── tools.py      web_search, python_executor, calculator
│   │   ├── shortcuts.py  Deterministic fast path (arithmetic, compound growth, statistics)
│   │   ├── prompts.py    SYSTEM_PROMPT with ReAct format and few-shot examples
│   │   ├── redaction.py  Secret redaction for logs and error messages
│   │   └── state.py      AgentState TypedDict, MaxIterationsError
│   ├── api.py            FastAPI routes, SSE streaming, CORS, rate limiting, trace store
│   ├── main.py           Standalone uvicorn entrypoint
│   └── tests/            Unit tests (agent, API, LLMs, redaction)
├── frontend/             React 19, TypeScript, Vite, TailwindCSS
│   └── src/
│       ├── App.tsx           Shell: resizable left sidebar, tab navigation (Chat / About)
│       ├── hooks/useAgent.ts SSE client, session persistence (localStorage), mock fallback
│       ├── components/
│       │   ├── ChatWorkspace.tsx     Chat + reasoning trace layout
│       │   ├── demo/ChatPanel.tsx    Message list, starter suggestions, contextual prompts
│       │   ├── demo/ReasoningPanel.tsx  Trace timeline with Thought/Action/Observe steps
│       │   ├── demo/TraceDock.tsx    Telemetry strip, progress bar, run metadata
│       │   ├── ui/animated-ai-chat.tsx  Auto-resizing input with send/clear controls
│       │   ├── PortfolioView.tsx     Landing page shell (Hero + HowItWorks + Stack + Footer)
│       │   ├── HeroSection.tsx       Above-the-fold hero with animated agent flow preview
│       │   ├── HowItWorksSection.tsx Three-card explainer + flow pipeline strip
│       │   └── StackSection.tsx      Technology table + GitHub CTA card
│       └── types/index.ts  Step, StreamEvent, AgentResponse, AgentState, AgentConfig
├── api/index.py          Vercel Python Function entrypoint (imports backend/api.py)
├── scripts/dev-vercel.mjs  Full-stack local dev wrapper (builds frontend, runs Vercel or uvicorn)
└── vercel.json           Build config + SPA rewrite rules
```

### Backend flow

Before building the graph, the API tries a local fast path for simple deterministic tasks: arithmetic, compound growth, square roots, and basic statistics with an explicit list. When it matches, the response preserves `trace/steps` but never calls an LLM provider.

`agent_node` calls the LLM with the `SYSTEM_PROMPT` (which includes the current date and current-fact rules), parses the response in ReAct format, and records `Thought`, `Action`, `Action Input`, or `Final Answer`. When the query requires current facts, it forces `web_search` before answering, even if the model tries to answer directly. A cap of 2 searches per run prevents search loops.

`tool_node` executes the chosen tool, creates a `Step` with `thought`, `action`, `action_input`, `observation`, and `timestamp`, then increments `iteration_count`.

`should_continue` is the graph router: it routes to `tool_node` when an `Action` exists, ends when a `Final Answer` exists, and raises `MaxIterationsError` at 10 iterations. Without this, a bad agent becomes a while loop with self-esteem.

### Frontend flow

The `useAgent` hook POSTs to `/api/run` with `stream: true`, parses SSE progressively (`parseSseEvents` + `sseDataFromEvent`), and converts each payload into a `Step` on the timeline. The session (messages + steps + runSummary) persists in `localStorage`. If `VITE_AGENT_MOCK=true`, it runs a mock sequence without an API. Connection state (`checking`, `online`, `mock`, `error`) is loaded via `/api/config`.

The interface has two tabs: **Chat** (conversation workspace with reasoning panel) and **About** (portfolio landing with hero, how it works, stack). The left sidebar is drag-resizable. The reasoning panel (right side on desktop) or bottom sheet (mobile) shows each step with a colored badge (Thought / Action / Observe / Final), timestamp, cycle, and tool/input/elapsed metadata.

## Diagram

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI["Chat UI"]
        Hook["useAgent Hook"]
        Trace["Reasoning Panel"]
        Portfolio["Portfolio View"]
    end

    subgraph Backend["Backend (FastAPI)"]
        API["POST /agent/invoke"]
        SC["Shortcut Engine"]
        subgraph LangGraph["LangGraph StateGraph"]
            AN["Agent Node<br/>(LLM Reasoning)"]
            TN["Tool Node<br/>(Execute)"]
            Router{"should_continue"}
        end
        Store["Trace Store<br/>(last 100 runs)"]
    end

    subgraph Tools["Tools"]
        WS["web_search<br/>(Tavily API)"]
        PE["python_executor<br/>(Subprocess sandbox)"]
        CA["calculator<br/>(AST-validated eval)"]
    end

    subgraph Providers["LLM Providers (fallback chain)"]
        G["Gemini"]
        GR["Groq"]
        GH["GitHub Models"]
        OR["OpenRouter"]
        CF["Cloudflare Workers AI"]
    end

    UI -->|"query + history"| Hook
    Hook -->|"POST SSE"| API
    API -->|"try fast path"| SC
    SC -->|"hit"| Store
    SC -->|"miss"| AN
    AN -->|"Thought + Action"| Router
    Router -->|"has Action"| TN
    Router -->|"has Final Answer"| Store
    Router -->|"≥ 10 iterations"| Store
    TN -->|"Observation"| AN
    TN --> WS
    TN --> PE
    TN --> CA
    AN -->|"invoke"| G
    G -.->|"fallback"| GR
    GR -.->|"fallback"| GH
    GH -.->|"fallback"| OR
    OR -.->|"fallback"| CF
    Store -->|"SSE events"| Hook
    Hook -->|"steps"| Trace
    Hook -->|"messages"| UI

    style Frontend fill:#1a1a2e,stroke:#8BD3FF,color:#fff
    style Backend fill:#1a1a2e,stroke:#F6C177,color:#fff
    style LangGraph fill:#0d0d1a,stroke:#D6FF7F,color:#fff
    style Tools fill:#1a1a2e,stroke:#7EE787,color:#fff
    style Providers fill:#1a1a2e,stroke:#A78BFA,color:#fff
```

## Tools

| Tool | Description | API |
| --- | --- | --- |
| `web_search` | Web search via Tavily returning compact results with title, URL, and truncated snippet. Defaults: `TAVILY_MAX_RESULTS=2`, `TAVILY_SNIPPET_CHARS=360`. | Tavily API (`TAVILY_API_KEY`) |
| `python_executor` | Runs code in an isolated subprocess with AST validation, import whitelist (`math`, `json`, `re`, `statistics`, `random`, `itertools`, `functools`, `sympy`, `numpy`), blocked builtins (`open`, `exec`, `eval`, `compile`, `__import__`, etc.), and a 10s timeout. Automatically strips Markdown fences and redundant safe imports. | Local subprocess sandbox |
| `calculator` | Evaluates math expressions with `eval()` and no builtins, AST validation of every node, and full access to the `math` module. Only arithmetic operators, constants, and `math.*` functions are allowed. | Local `math` module |

## Model Providers

The agent does not use OpenAI or Anthropic. The default chain uses only providers configured in `.env`, in this fallback order:

1. `GEMINI_API_KEY` with `GEMINI_MODEL`, default `gemini-2.5-flash`
2. `GROQ_API_KEY` with `GROQ_MODEL`, default `llama-3.3-70b-versatile`
3. `GITHUB_MODELS_TOKEN` + `GITHUB_MODELS_MODEL`
4. `OPENROUTER_API_KEY` with `OPENROUTER_MODEL`, default `meta-llama/llama-3.1-8b-instruct:free`
5. `CF_ACCOUNT_ID` + `CF_WORKERS_AI_TOKEN` with `CF_WORKERS_AI_MODEL`, default `@cf/meta/llama-3-8b-instruct`

`FreeModelFallback` tries each provider in order. If one fails, it skips to the next. If all fail, it raises `RuntimeError` with concatenated errors (secrets redacted). The `/config` endpoint returns the active model and fallbacks; the frontend displays this in the chat status bar.

These providers may have their own quotas, terms, and limits. For absolute zero cost, run a local model and adapt `agent/llms.py`; a free cloud API is still a cloud API, not a contractual miracle.

## Frontend

| Component | Responsibility |
| --- | --- |
| `App.tsx` | Shell: resizable left sidebar, desktop/mobile toggle, Chat/About tabs, shell state persistence in localStorage |
| `ChatWorkspace` | Two-column layout: chat + reasoning panel. Header with status, active model, and available tools |
| `ChatPanel` | Message list, empty state with starter suggestions, contextual post-response suggestions, auto-scroll |
| `ReasoningPanel` | Animated timeline (Framer Motion) of steps with color-coded badges by type, cycle, timestamp, tool metadata. Telemetry strip with steps/tools/time. Progress bar. Desktop: resizable right sidebar. Mobile: Radix Dialog bottom sheet |
| `AnimatedAIChat` | Auto-resize textarea, Enter to submit, clear history, loading state |
| `PortfolioView` | Landing page: HeroSection (title + CTA + animated agent flow preview), HowItWorksSection (3 cards + pipeline strip), StackSection (stack table + GitHub card), PageFooter |
| `useAgent` | Core hook: fetch config, SSE streaming, session persistence, mock fallback, state machine (checking → online/mock/error) |

## API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/agent/invoke` | POST | Run agent (JSON or SSE with `stream:true`). Accepts `query`, `stream`, `history[]`. |
| `/run` | POST | Backward-compatible alias for `/agent/invoke` |
| `/run` | GET | Streaming via query param `?query=...&stream=true` |
| `/health` | GET | Status + list of available tools |
| `/config` | GET | Active model, fallbacks, tools. Used by the frontend on boot |
| `/trace/{run_id}` | GET | Returns the stored `AgentResponse` for a previous run lookup |

All endpoints are duplicated with an `/api/` prefix for Vercel routing compatibility.

Streaming emits SSE payloads in this shape:

```json
{"type":"thought|action|observation|final","content":"...","step":1,"timestamp":"...","status":"running","tool":"web_search","action_input":"...","run_id":"abc123","elapsed_ms":142}
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Full-stack (Vercel local)

```bash
npm run dev:vercel
```

The wrapper `scripts/dev-vercel.mjs` builds `frontend/dist`, clears `VIRTUAL_ENV` so Vercel detects the correct venv, binds to `127.0.0.1:3000`, and falls back to `uvicorn api.index:app` if `@vercel/python` fails to start on Windows/Git Bash.

## Deploy

```bash
vercel
```

Vercel builds the frontend via `cd frontend && npm install && npm run build`, serves static assets from `frontend/dist`, and routes everything to `api/index.py` which imports the FastAPI app from the backend.

## Validate

```bash
# Backend tests
cd backend && python -m unittest discover -s tests -v

# Frontend lint + build
cd frontend && npm run lint && npm run build

# Secret scan (before publishing)
.\scripts\check-secrets.ps1
```

The secret scan ignores `.env`, `node_modules`, and `dist`, then checks source, docs, and config for common provider token patterns.

## Problem

LLM agents usually fail in the boring places: invisible reasoning, unbounded loops, mixed tool side effects, and APIs that return only the final answer. That is cute in a demo and radioactive in anything operational. On the frontend side, most agent demos either dump raw JSON or show a loading spinner until everything is done. Neither tells the user anything useful while the agent is still working.

## Solution

This project wraps a ReAct loop in LangGraph, exposes it through FastAPI with both sync and SSE modes, and stores the last 100 runs in memory for trace lookup. The React frontend consumes the SSE stream progressively, rendering each Thought, Action, and Observation step in a colored timeline as it arrives. The chat answer and the reasoning trace that produced it are always visible side by side.

`/agent/invoke` is the portfolio-facing endpoint, `/run` remains as a backward-compatible alias, `/health` lists available tools, `/config` gives the frontend everything it needs to render model status, and `/trace/{run_id}` returns the stored `AgentResponse`.

## Why This Solves It

**Backend:** LangGraph makes control flow explicit: reason, route, execute tool, observe, repeat, stop. Each tool call becomes a `Step`, so debugging is not archaeology. SSE exposes progress while the run is happening, which matters when a user needs to see whether the agent is thinking, acting, or stuck writing fanfic about acting.

**Frontend:** The split-pane layout (chat + reasoning trace) eliminates the "black box" problem. The timeline is not an afterthought panel — it is the core differentiation. Framer Motion animations, step badges, telemetry counters, and resizable panels make the reasoning visible and inspectable without requiring the user to open DevTools.

**Shortcuts:** Deterministic fast paths for arithmetic, compound growth, square roots, and basic statistics mean the agent does not waste an LLM call on `2 + 2`. The trace still shows the step, so the UI stays consistent.

**Security:** `python_executor` runs in a subprocess with AST validation, import whitelist, blocked builtins, and a 10s timeout. `redaction.py` scrubs secrets from all log output and error messages. Rate limiting via slowapi caps at 10 req/min/IP.

## Metrics

| Metric | Value |
| --- | --- |
| Max ReAct iterations | `10` |
| Stored traces | Last `100` runs |
| Rate limit | `10 req/min/IP` |
| Local shortcuts | Arithmetic, compound growth, square roots, basic statistics |
| Web search context | `2` results, `360` chars per snippet by default |
| Web search cap per run | `2` (prevents search loops) |
| Tools available | `3` (`web_search`, `python_executor`, `calculator`) |
| API modes | Sync JSON + SSE streaming |
| Chat history sent | Last `8` messages |
| Session persistence | localStorage (messages + steps + runSummary) |
| Frontend tabs | Chat, About (portfolio) |
| Test coverage | Unit tests for tools, graph flow, shortcuts, health, run, stream, trace, LLMs, redaction |

## Key Decisions

**Why LangGraph over AgentExecutor:** LangGraph gives explicit nodes, router logic, state transitions, and a hard iteration boundary. `AgentExecutor` is convenient, but the control flow is more implicit. Implicit agent control flow is how debugging becomes interpretive dance.

**Why SSE over WebSockets:** The agent already produces sequential events: thought, action, observation, final. SSE maps to that shape without WebSocket ceremony. One request, ordered events, easy `curl -N`, done. The frontend parses SSE chunks progressively with a manual buffer, not EventSource, to handle Vercel edge proxying and partial flushes.

**Why subprocess for python_executor:** `exec()` in-process is a sandbox escape waiting to happen. A subprocess with AST validation, import whitelisting, and a 10s timeout is defense in depth. The subprocess pre-loads sympy and numpy (when available) so the agent does not waste a step importing them.

**Why FreeModelFallback:** Portfolio projects should not cost money to run. The fallback chain means if Gemini's free tier rate-limits, Groq picks up. If Groq is down, OpenRouter gets a shot. The user never sees a failed run unless every provider is genuinely unreachable.

**Why shortcuts exist:** Calling an LLM to compute `12 * 8 + 5` is wasteful. The shortcut engine handles arithmetic, compound growth, square roots, and basic statistics deterministically. The trace still shows the step with tool attribution, so the frontend does not need a separate code path.

**How MaxIterationsError works:** `should_continue` checks `iteration_count` before routing back into tools. At `10`, it raises `MaxIterationsError` instead of letting the loop continue. This makes runaway reasoning fail loudly instead of charging rent in your process.

**Why redaction exists:** API keys leak through error messages more often than through `.env` files. `redaction.py` scrubs all configured secret values from log output and exception strings, including query parameters and Bearer tokens. The log record factory is monkey-patched at startup so every log line is automatically redacted.

## Environment

Copy `backend/.env.example` to `backend/.env` and configure:

```env
# At least one LLM provider required
GEMINI_API_KEY=
GROQ_API_KEY=
GITHUB_MODELS_TOKEN=
GITHUB_MODELS_MODEL=
OPENROUTER_API_KEY=
CF_ACCOUNT_ID=
CF_WORKERS_AI_TOKEN=

# Web search (optional but recommended)
TAVILY_API_KEY=
```

Frontend env (optional):

```env
VITE_API_URL=http://localhost:8000   # default: /api
VITE_AGENT_MOCK=true                 # run without backend
```
