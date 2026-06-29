# Technology Stack

**Analysis Date:** 2026-06-29

## Languages

**Primary:**
- Python 3.11 - Backend API, ReAct agent, tools, evaluation harness
- TypeScript - Frontend UI, React components, type definitions
- JavaScript - Build tooling, Vercel integration

**Secondary:**
- HTML/CSS - UI markup and styling (via TailwindCSS)

## Runtime

**Environment:**
- Python 3.11 (pinned: `numpy 1.26.4` has no Python 3.14 wheel; use `uv venv --python 3.12` if 3.14 required)
- Node.js with npm (frontend development and build)

**Package Manager:**
- pip - Python dependencies in `backend/requirements.txt`
- npm - JavaScript dependencies in `frontend/package.json`
- Lockfiles: `frontend/package-lock.json` present

## Frameworks

**Core Backend:**
- FastAPI 0.115.4 - REST API framework, SSE streaming, CORS, rate limiting
- LangGraph 0.2.45 - ReAct agent state graph (2-node: agent_node ↔ tool_node)
- Starlette 0.41.3 - ASGI web framework (FastAPI built on Starlette)
- Uvicorn 0.32.0 - ASGI server for local development and production (`python -m uvicorn api:app`)

**Core Frontend:**
- React 19 - UI framework and component library
- Vite 8 - Build tool and dev server, configured with React plugin
- TypeScript ~6.0.2 - Type-safe JavaScript for frontend

**Styling & UI:**
- TailwindCSS 3.4 - Utility-first CSS framework
- Framer Motion 12.38.0 - Animation library for reasoning panel timeline
- Radix UI - Headless component library (`@radix-ui/react-dialog`, `@radix-ui/react-tooltip`)
- lucide-react 1.11.0 - Icon library
- PostCSS 8.5.12 - CSS transformation (required by TailwindCSS)
- Autoprefixer 10.5.0 - CSS vendor prefixing

**Content & Rendering:**
- react-markdown 10.1.0 - Markdown rendering in chat messages
- react-syntax-highlighter 16.1.1 - Code block syntax highlighting
- remark-gfm 4.0.1 - GitHub Flavored Markdown support for react-markdown

**Testing & Validation:**
- Python unittest - Backend unit tests (`backend/tests/`)
- No frontend test framework configured

**Build & Development:**
- ESLint 10.2.1 - JavaScript/TypeScript linting
- TypeScript ESLint 8.58.2 - TypeScript-specific linting rules
- ESLint plugins: `react-hooks`, `react-refresh`
- Globals 17.5.0 - Global variable definitions for browser environments

## Key Dependencies

**Critical Backend:**
- langchain 0.3.7 - LLM framework abstractions
- langchain-core 0.3.63 - Base classes for chains, messages, tools
- langchain-community 0.3.7 - Community integrations
- Pydantic 2.13.3 - Data validation and settings management
- python-dotenv 1.0.1 - Environment variable loading from `.env`

**HTTP & Networking:**
- httpx 0.28.1 - Async HTTP client (used for LLM provider calls)
- requests 2.33.1 - Synchronous HTTP client
- urllib3 2.6.3 - Low-level HTTP utilities

**Math & Computation:**
- sympy 1.14.0 - Symbolic mathematics library (optional import for python_executor)
- numpy 1.26.4 - Numeric computing (optional import for python_executor)
- mpmath 1.3.0 - Arbitrary-precision arithmetic (dependency of sympy)

**API & Streaming:**
- sse-starlette 2.1.3 - Server-Sent Events support for streaming responses
- httpx-sse 0.4.3 - SSE utilities for httpx
- slowapi 0.1.9 - Rate limiting (10 req/min/IP default)

**Token & Usage Tracking:**
- tiktoken 0.12.0 - OpenAI token counter for usage tracking
- tenacity 9.1.4 - Retry library with exponential backoff (for LLM calls)

**Utilities:**
- Pydantic settings 2.14.0 - Configuration management
- PyYAML 6.0.3 - YAML parsing
- marshmallow 3.26.2 - Object serialization
- SQLAlchemy 2.0.35 - ORM (imported but minimal use; agent uses in-memory storage)
- tqdm 4.67.3 - Progress bars for evaluation runs

**Async & Concurrency:**
- aiohttp 3.13.5 - Async HTTP client
- aiohappyeyeballs 2.6.1 - Happy Eyeballs protocol for faster connections
- aiosignal 1.4.0 - Signal support for async code

**LangGraph & Dependencies:**
- langgraph 0.2.45 - State graph for agent orchestration
- langgraph-checkpoint 2.1.2 - State persistence checkpoints
- langgraph-sdk 0.1.74 - SDK tools
- langsmith 0.1.147 - LangChain observability and tracing

## Configuration

**Environment:**
- `.env` file (not in version control, see `.env.example`) configures:
  - LLM provider keys: `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_MODELS_TOKEN`, `GITHUB_MODELS_MODEL`
  - Per-role provider preferences: `RESPONDER_PROVIDER` (default: gemini), `SUGGESTER_PROVIDER` (default: groq)
  - Web search: `TAVILY_API_KEY`
  - Frontend API URL (optional): `VITE_API_URL` (default: /api)
  - Mock mode toggle: `VITE_AGENT_MOCK=true` (skip backend, use local mock)
  - Debug flags: `REACT_AGENT_SKIP_DOTENV`, `REACT_AGENT_DISABLE_WEB_SEARCH_GATE`, `PYTHON_EXECUTOR_TIMEOUT_SECONDS` (1–60s, default 30s)

**Frontend Build:**
- `vite.config.ts` - Vite configuration with React plugin and `@` path alias to `src/`
- `tsconfig.json` - References `tsconfig.app.json` and `tsconfig.node.json`
- `eslint.config.js` - Flat ESLint config with React and TypeScript rules

**Backend Build:**
- `vercel.json` - Vercel deployment config: frontend build (`cd frontend && npm install && npm run build`), static output to `frontend/dist`, rewrites to `api/index.py`
- `pyrightconfig.json` - Pyright type checking configuration (minimal)

**API Entrypoint:**
- `api/index.py` - Vercel Python Function entrypoint; loads `backend/api.py` by file path and re-exports `app`
- `backend/api.py` - FastAPI application definition with all routes

## Platform Requirements

**Development:**
- Python 3.11+ (or 3.12 if using latest Node tooling)
- Node.js + npm for frontend
- Virtual environment for backend isolation
- Git for version control

**Production:**
- Vercel (full-stack hosting): builds frontend, runs Python backend via `@vercel/python`
- Fallback: Can run locally with `python -m uvicorn api:app` and serve frontend from `frontend/dist`

**Local Dev Commands:**
- Backend: `python -m uvicorn api:app --reload --port 8000` (from `backend/`)
- Frontend: `npm run dev` (from `frontend/`)
- Full-stack: `npm run dev:vercel` (from repo root) — uses `scripts/dev-vercel.mjs` wrapper

---

*Stack analysis: 2026-06-29*
