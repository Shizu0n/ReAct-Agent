# Codebase Structure

**Analysis Date:** 2026-06-29

## Directory Layout

```
react-agent/
├── backend/                      FastAPI app, LangGraph agent, tools, tests, evals
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py              2-node StateGraph (agent_node ↔ tool_node), routing, web search guardrail
│   │   ├── llms.py               FreeModelFallback, provider preferences, usage tracking
│   │   ├── tools.py              web_search, python_executor, calculator (tools + validation)
│   │   ├── suggestions.py         Conversation-aware suggester (Groq-preferred, static fallback)
│   │   ├── prompts.py            SYSTEM_PROMPT for native tool calling
│   │   ├── redaction.py          Secret scrubbing from logs
│   │   └── state.py              AgentState TypedDict, MaxIterationsError exception
│   ├── api.py                    FastAPI routes, SSE streaming, trace store, rate limiting
│   ├── main.py                   Scripted ReAct demo (fake LLM, no API keys required)
│   ├── evals/
│   │   ├── __init__.py
│   │   ├── evaluate.py           Agent evaluation harness (task success + tool selection scoring)
│   │   ├── cases.jsonl           Test cases (id, category, query, expect_tools, checks)
│   │   ├── baseline.json         Published eval results (served at GET /evals)
│   │   └── README.md             Eval harness documentation
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_agent.py         LangGraph flow, state transitions, iteration limits
│   │   ├── test_api.py           HTTP endpoints, SSE streaming, trace storage
│   │   ├── test_llms.py          Provider fallback, usage tracking
│   │   ├── test_redaction.py     Secret redaction in logs
│   │   └── test_suggestions.py    Suggester output validation
│   ├── .env.example              Environment variable template (Gemini, Groq, GitHub, Tavily keys)
│   ├── .env                      (git-ignored) Filled .env.example with actual keys
│   ├── requirements.txt          Python dependencies (FastAPI, LangGraph, providers)
│   └── .venv/                    (git-ignored) Python virtual environment
├── frontend/                     React 19, TypeScript, Vite, TailwindCSS
│   ├── src/
│   │   ├── App.tsx               Shell: resizable left sidebar, tab nav (Chat/About), desktop/mobile toggle
│   │   ├── main.tsx              React 19 entry point
│   │   ├── components/
│   │   │   ├── ChatWorkspace.tsx       Two-column layout: chat + reasoning panel
│   │   │   ├── PortfolioView.tsx       Landing page shell (hero, how it works, stack, footer)
│   │   │   ├── DemoSection.tsx         Chat demo section (embedded on portfolio)
│   │   │   ├── EvalsSection.tsx        Evaluation results visualization
│   │   │   ├── HeroSection.tsx         Above-the-fold hero with agent flow preview
│   │   │   ├── HowItWorksSection.tsx   Three-card explainer + pipeline strip
│   │   │   ├── StackSection.tsx        Technology table + GitHub CTA card
│   │   │   ├── PageFooter.tsx          Footer
│   │   │   ├── ProjectMark.tsx         Logo/icon component
│   │   │   ├── demo/
│   │   │   │   ├── ChatPanel.tsx       Message list, static starter prompts, server-generated suggestions
│   │   │   │   ├── ReasoningPanel.tsx  Animated timeline (Framer Motion) of Thought/Action/Observe steps
│   │   │   │   ├── TraceDock.tsx       Telemetry strip (steps, tools, time, progress bar)
│   │   │   │   └── MessageMarkdown.tsx Markdown rendering with syntax highlighting
│   │   │   ├── hero/
│   │   │   │   ├── AgentFlowPreview.tsx Animated agent flow diagram (scroll-driven)
│   │   │   │   └── ScrollCue.tsx        Scroll indicator animation
│   │   │   └── ui/
│   │   │       └── animated-ai-chat.tsx Auto-resizing textarea with send/clear controls
│   │   ├── hooks/
│   │   │   └── useAgent.ts       SSE client, session persistence (localStorage), mock fallback, state machine
│   │   ├── lib/
│   │   │   └── utils.ts          Utility functions (SSE parsing, etc.)
│   │   ├── types/
│   │   │   └── index.ts          TypeScript interfaces (Step, AgentResponse, AgentState, etc.)
│   │   └── index.css             Global styles (TailwindCSS)
│   ├── public/                   Static assets (favicon, etc.)
│   ├── dist/                     (git-ignored) Built frontend (Vite build output)
│   ├── package.json              Dependencies, build scripts, versions
│   ├── package-lock.json         Lock file
│   ├── tsconfig.json             TypeScript config
│   ├── vite.config.ts            Vite config with React plugin, @ alias
│   ├── .eslintrc.cjs             Linting config
│   ├── .prettierrc                Formatting config
│   ├── tailwind.config.js        TailwindCSS config
│   ├── README.md                 Frontend-specific docs
│   └── node_modules/             (git-ignored) npm dependencies
├── api/
│   └── index.py                  Vercel Python Function entrypoint (imports backend/api.py)
├── scripts/
│   └── dev-vercel.mjs            Full-stack local dev wrapper (builds frontend, runs vercel or uvicorn)
├── .planning/
│   └── codebase/                 (Auto-generated) Architecture/structure/conventions analysis
│       ├── ARCHITECTURE.md
│       ├── STRUCTURE.md
│       ├── CONVENTIONS.md
│       ├── TESTING.md
│       ├── STACK.md
│       ├── INTEGRATIONS.md
│       └── CONCERNS.md
├── graphify-out/                 (Auto-generated) Knowledge graph output (AST + semantic)
├── .git/                         Git repository
├── .gitignore                    Ignore rules (.venv, node_modules, .env, dist, etc.)
├── README.md                     Main documentation (architecture overview, quick start, deploy)
├── CLAUDE.md                     Developer instructions (commands, layout gotchas, invariants)
├── package.json                  Root-level scripts (npm run dev:vercel)
├── vercel.json                   Vercel deployment config (build, rewrite rules)
├── pyrightconfig.json            Pyright type checking config
└── requirements.txt              Root-level Python requirements summary
```

## Directory Purposes

**backend/:**
- Purpose: FastAPI application, LangGraph ReAct agent, tools, tests, evaluation harness
- Contains: Python source code, virtual environment, test suite, eval dataset/baseline
- Key files: `api.py` (routes), `agent/graph.py` (StateGraph), `requirements.txt` (dependencies)

**backend/agent/:**
- Purpose: Agent logic, LLM provider integration, tools, suggestions, redaction
- Contains: LangGraph nodes, LLM wrapper, three tools, suggestions engine, security utilities
- Organization: Each module has a single responsibility (graph, llms, tools, etc.)

**backend/evals/:**
- Purpose: Agent evaluation harness and baseline results
- Contains: Evaluation runner, test cases (JSONL format), published baseline (JSON)
- Outputs: baseline.json (served at GET /evals, displayed on About page)

**backend/tests/:**
- Purpose: Unit tests for agent, API, LLMs, redaction, suggestions
- Contains: Test modules mirroring backend structure
- Pattern: unittest framework; each test file targets one module

**frontend/src/:**
- Purpose: React source code (components, hooks, types, styles)
- Contains: Component tree (App → ChatWorkspace/PortfolioView), hooks, TypeScript types, CSS
- Organization: `components/` (UI components), `hooks/` (state logic), `types/` (TypeScript types)

**frontend/src/components/demo/:**
- Purpose: Chat interface components (not portfolio landing)
- Contains: ChatPanel, ReasoningPanel, TraceDock, MessageMarkdown
- Used by: ChatWorkspace (when on Chat tab)

**frontend/src/components/hero/:**
- Purpose: Animated sections for portfolio landing page
- Contains: AgentFlowPreview, ScrollCue
- Used by: HeroSection

**frontend/src/components/ui/:**
- Purpose: Reusable UI primitives (animated input, etc.)
- Contains: animated-ai-chat (auto-resizing textarea)

**frontend/public/:**
- Purpose: Static assets served as-is (favicon, etc.)
- Served by: Vite dev server and production build

**api/:**
- Purpose: Vercel Python Function entrypoint (bridges Vercel routing to backend)
- Contains: Single file that imports and re-exports backend/api.py:app
- Why separate: Vercel expects /api/*.py as serverless functions; this lets vercel.json route to it

**scripts/:**
- Purpose: Development tooling
- Contains: dev-vercel.mjs (full-stack local dev wrapper)
- Usage: `npm run dev:vercel` builds frontend, then starts vercel/uvicorn on 127.0.0.1:3000

**.planning/codebase/:**
- Purpose: Auto-generated architecture documentation
- Created by: `/gsd-map-codebase` (this agent)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md
- Used by: `/gsd-plan-phase`, `/gsd-execute-phase` for context

**graphify-out/:**
- Purpose: Knowledge graph (AST + semantic edges)
- Created by: `graphify` skill
- Contents: cache/ast and cache/semantic subdirectories with node/edge data
- Used by: Graph queries (`graphify query`, `graphify path`, etc.)

## Key File Locations

**Entry Points:**
- `frontend/src/main.tsx` - React 19 entry point
- `frontend/src/App.tsx` - App shell component
- `backend/api.py` - FastAPI app definition (uvicorn target)
- `api/index.py` - Vercel Python Function entrypoint

**Configuration:**
- `backend/.env.example` - Environment variable template
- `backend/requirements.txt` - Python dependencies
- `frontend/package.json` - npm dependencies and build scripts
- `frontend/vite.config.ts` - Vite build config
- `frontend/tsconfig.json` - TypeScript config
- `vercel.json` - Vercel build and routing config
- `CLAUDE.md` - Developer instructions (this repo's conventions)

**Core Logic:**
- `backend/agent/graph.py` - LangGraph StateGraph (agent_node, tool_node, should_continue)
- `backend/agent/llms.py` - FreeModelFallback provider chain
- `backend/agent/tools.py` - web_search, python_executor, calculator
- `backend/api.py` - FastAPI routes and SSE streaming
- `frontend/src/hooks/useAgent.ts` - SSE client, session persistence, state machine

**State & Types:**
- `backend/agent/state.py` - AgentState, Step, MaxIterationsError TypedDicts/exceptions
- `frontend/src/types/index.ts` - TypeScript interfaces (Step, AgentResponse, AgentState, etc.)

**Testing:**
- `backend/tests/test_agent.py` - Agent flow, state transitions, iteration limits
- `backend/tests/test_api.py` - HTTP endpoints, SSE streaming, trace storage
- `backend/tests/test_llms.py` - Provider fallback, usage tracking
- `backend/evals/cases.jsonl` - Evaluation test cases
- `backend/evals/baseline.json` - Published eval results

## Naming Conventions

**Files:**
- Backend: `snake_case.py` (graph.py, llms.py, test_agent.py)
- Frontend: PascalCase for components (`ChatWorkspace.tsx`), camelCase for hooks/utilities (`useAgent.ts`, `utils.ts`)
- Config: lowercase with dots (`.env`, `vite.config.ts`, `tsconfig.json`)

**Directories:**
- Backend: `snake_case/` (agent/, evals/, tests/)
- Frontend: `camelCase/` or lowercase (src/, components/, hooks/, lib/, types/, public/, dist/)
- Special: `.git/`, `.venv/`, `.next/` (hidden dirs for tooling)

**Functions:**
- Python: `snake_case` (build_graph, agent_node, _requires_web_search, _stream_agent)
- TypeScript: `camelCase` (useAgent, parseSseEvents, readShellState)
- React components: PascalCase (App, ChatWorkspace, ReasoningPanel)

**Variables:**
- Python constants: `UPPER_CASE` (MAX_ITERATIONS, TOOL_SCHEMAS, WEB_SEARCH_GATE_DISABLE_ENV)
- Python module-level: `snake_case` (limiter, logger, RUNS, RUN_ORDER)
- TypeScript state: `camelCase` (isLoading, connectionStatus, traceOpen)
- React props: `camelCase` (query, history, tools_used)

**Types/Classes:**
- Python: PascalCase (AgentState, MaxIterationsError, ChatMessageRequest, AgentResponse)
- TypeScript: PascalCase interfaces (AgentState, Step, AgentResponse, Message)

**Module Exports:**
- Python: App object, helper functions (build_graph, agent_node, web_search, calculator, etc.)
- TypeScript: Named exports (useAgent hook, interfaces, type aliases)

## Where to Add New Code

**New Frontend Feature:**
- Component: `frontend/src/components/[ComponentName].tsx`
- Hook for state logic: `frontend/src/hooks/use[Feature].ts`
- Types: Add to `frontend/src/types/index.ts`
- Tests: Would go in frontend/tests/ (currently none, but follow backend pattern)

**New Backend Tool:**
- Tool implementation: Add function to `backend/agent/tools.py`
- Tool schema: Add to `TOOL_SCHEMAS` array in `backend/agent/graph.py`
- Tool registry: Register in `TOOLS` dict in `backend/agent/graph.py`
- Tool input key: Add to `TOOL_INPUT_KEYS` dict in `backend/agent/graph.py`
- Tests: Add test case to `backend/tests/test_agent.py` or new test file

**New API Endpoint:**
- Route handler: Add @app.post/get decorator to `backend/api.py`
- Request/response model: Add Pydantic class to `backend/api.py`
- Register both bare and `/api/`-prefixed paths (for Vercel compatibility)
- Update `vercel.json` rewrite rules if adding new route

**New LLM Provider:**
- Provider integration: Add to `FreeModelFallback.invoke()` in `backend/agent/llms.py`
- Configuration: Add env var handling to `load_model_environment()`
- Preferences: Add to `providers_preferring()` if it should be a preferred role
- Tests: Add provider test to `backend/tests/test_llms.py`

**New Suggestion Strategy:**
- Logic: Modify `generate_suggestions()` in `backend/agent/suggestions.py`
- Fallback: Update `FALLBACK_SUGGESTIONS` list
- Tests: Add test to `backend/tests/test_suggestions.py`

**New Evaluation Category:**
- Cases: Add JSONL lines to `backend/evals/cases.jsonl` with new category
- Scoring: Modify `backend/evals/evaluate.py` if special scoring logic needed
- Baseline: Regenerate with `python -m evals.evaluate --publish` (burns quota!)

**Shared Utilities:**
- Frontend utils: `frontend/src/lib/utils.ts`
- Backend utils: Could be added to existing modules or new module (be conservative)

**Secrets/Config:**
- Environment handling: `backend/agent/llms.py` for LLM keys, `backend/agent/tools.py` for tool API keys
- Redaction: Add to `SECRET_VALUES` in `backend/agent/redaction.py` if new sensitive value needs scrubbing

## Special Directories

**backend/.venv/:**
- Purpose: Python virtual environment (isolated dependencies)
- Generated: Yes (run `pip install -r requirements.txt`)
- Committed: No (.gitignore)
- Platform-specific: Yes (Win/Mac/Linux have different binaries)

**frontend/node_modules/:**
- Purpose: npm dependencies
- Generated: Yes (run `npm install`)
- Committed: No (.gitignore)
- Platform-specific: No (JS is cross-platform)

**frontend/dist/:**
- Purpose: Vite build output (bundled frontend)
- Generated: Yes (run `npm run build`)
- Committed: No (.gitignore)
- Used by: Vercel build or local uvicorn (fallback when vercel dev unavailable)

**graphify-out/:**
- Purpose: Knowledge graph (AST + semantic analysis)
- Generated: Yes (run `graphify update .`)
- Committed: Maybe (optional optimization; not required)
- Used by: Graph queries for architecture questions

**.planning/codebase/:**
- Purpose: Architecture/structure/conventions analysis
- Generated: Yes (run `/gsd-map-codebase` with focus: arch/tech/quality/concerns)
- Committed: Yes (checked in to repo, used by planner/executor)
- Owned by: GSD orchestrator (do not manually edit; re-run to update)

## Build & Runtime Structure

**Local Development:**
```bash
# Backend only
cd backend && python -m uvicorn api:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Full-stack (Vercel local emulation)
npm run dev:vercel  # Runs vercel dev on 127.0.0.1:3000
```

**Production Build:**
```bash
# Frontend
cd frontend && npm run build  # Outputs to dist/

# Backend (no build needed; Python files are source)
# Vercel installs requirements.txt automatically

# Deployment
vercel  # Pushes to Vercel, triggers build
```

**Build Pipeline (Vercel):**
1. `cd frontend && npm install && npm run build` (Vite bundles to dist/)
2. Vercel serves dist/ as static files
3. `api/index.py` imports backend/api.py:app and handles all /api/ routes
4. vercel.json rewrites /run, /health, etc. to /api/ prefix

---

*Structure analysis: 2026-06-29*
