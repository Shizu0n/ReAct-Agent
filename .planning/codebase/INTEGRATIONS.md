# External Integrations

**Analysis Date:** 2026-06-29

## APIs & External Services

**LLM Providers (Fallback Chain):**
- Google Gemini - Default responder for agent answers
  - SDK/Client: `langchain` OpenAI-compatible endpoint at `https://generativelanguage.googleapis.com/v1beta/openai/`
  - Auth: `GEMINI_API_KEY` environment variable
  - Model: Configurable via `GEMINI_MODEL`, default `gemini-2.5-flash`
  - Implementation: `backend/agent/llms.py` - `GeminiProvider` class via OpenAI-compatible interface

- Groq - Default suggester for prompt suggestions, secondary responder fallback
  - SDK/Client: `langchain` OpenAI-compatible endpoint at `https://api.groq.com/openai/v1/`
  - Auth: `GROQ_API_KEY` environment variable
  - Model: Configurable via `GROQ_MODEL`, default `llama-3.3-70b-versatile`
  - Implementation: `backend/agent/llms.py` - `GroqProvider` class via OpenAI-compatible interface

- GitHub Models - Tertiary fallback LLM provider
  - SDK/Client: OpenAI-compatible endpoint at `https://models.inference.ai.azure.com/`
  - Auth: `GITHUB_MODELS_TOKEN` (GitHub personal access token) and `GITHUB_MODELS_MODEL` (full model name)
  - Implementation: `backend/agent/llms.py` - `GitHubModelsProvider` class via OpenAI-compatible interface

**Search:**
- Tavily - Web search for current facts and external information
  - SDK/Client: `tavily-python 0.5.0`
  - Auth: `TAVILY_API_KEY` environment variable
  - Usage: `backend/agent/tools.py` - `web_search` tool
  - Configuration: `TAVILY_MAX_RESULTS` (default 2), `TAVILY_SNIPPET_CHARS` (default 360)
  - Rate limit: Max 2 web searches per run (hard cap in `agent_node` to prevent search loops)

## Data Storage

**Databases:**
- None - The agent does not use a persistent database
- In-Memory Store: `backend/api.py` maintains `RUNS` dict with last 100 trace objects
  - Structure: `{"run_id": AgentResponse}`
  - Retention: Last 100 runs per process; lost on restart
  - Access: `/trace/{run_id}` endpoint returns stored `AgentResponse` for trace lookup

**Session & Client-Side Storage:**
- localStorage (browser) - Frontend session persistence
  - Key: `react-agent:chat-session:v1`
  - Contents: Messages, steps, and runSummary (user conversation history)
  - Scope: Per browser/domain; persists across page reloads
  - Implementation: `frontend/src/hooks/useAgent.ts` - `readPersistedSession()` and `persistSession()`

**File Storage:**
- None for runtime operation
- Build artifacts: `frontend/dist/` (static assets built on deploy)
- Evaluation baseline: `backend/evals/baseline.json` (committed JSON snapshot of eval results)

**Caching:**
- None - No cache layer (HTTP caching headers set to no-cache, no-store for SPA)

## Authentication & Identity

**Auth Provider:**
- None - No user authentication or identity system
- API is open (CORS allows all origins)
- Rate limiting by IP address (slowapi: 10 req/min/IP)

**API Keys:**
All configuration is environment-based; no runtime auth tokens or session management:
- `GEMINI_API_KEY` - Google Cloud API key
- `GROQ_API_KEY` - Groq cloud API key
- `GITHUB_MODELS_TOKEN` - GitHub personal access token
- `TAVILY_API_KEY` - Tavily web search API key

## Monitoring & Observability

**Error Tracking:**
- None - No third-party error tracking (Sentry, etc.)
- Logs to stdout via Python logging module
- Secrets redacted globally via `backend/agent/redaction.py`

**Usage Tracking:**
- Token counting via `tiktoken 0.12.0` (OpenAI token counter)
- Implementation: `backend/agent/llms.py` - `UsageTracker` class
- Metrics tracked per run:
  - `llm_calls` - Number of LLM invocations
  - `input_tokens` - Total tokens sent to LLM
  - `output_tokens` - Total tokens received from LLM
  - `total_tokens` - Sum of input + output
  - `estimated_cost_usd` - Rough cost estimate based on provider rates
  - `providers` - List of providers used in fallback chain
- Surfaced in: API response `usage` field, frontend telemetry strip

**Logs:**
- Python logging to stdout (level: INFO by default)
- Log redaction: `redaction.py` monkey-patches log factory to scrub secrets by name pattern (KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL)
- Suppressed verbose logs: httpx, httpcore, uvicorn.access set to WARNING

**Evaluation:**
- Evaluation harness: `backend/evals/evaluate` - runs agent against labeled test cases
- Dataset: `backend/evals/cases.jsonl` - one JSON case per line (id, category, query, expect_tools, checks)
- Baseline: `backend/evals/baseline.json` - committed summary served at `GET /evals`
- Metrics: Task success rate, tool selection accuracy
- Not a CI gate; manual baseline regeneration with `--publish` flag when quota is healthy

## CI/CD & Deployment

**Hosting:**
- Vercel (primary)
  - Config: `vercel.json` specifies:
    - Build: `cd frontend && npm install && npm run build`
    - Output directory: `frontend/dist`
    - Rewrites: All routes except static assets → `api/index.py`
    - Cache-Control headers: `no-cache, no-store, must-revalidate` for HTML
  - Python Runtime: `@vercel/python` (serverless)
  - Node Runtime: Vercel's default for JavaScript/TypeScript

**Local Development:**
- `scripts/dev-vercel.mjs` - Full-stack dev wrapper
  - Builds frontend to `frontend/dist`
  - Clears `VIRTUAL_ENV` so Vercel detects local venv correctly
  - Binds to `127.0.0.1:3000`
  - Falls back to `uvicorn api.index:app` if `@vercel/python` fails (common on Windows/Git Bash)

**CI Pipeline:**
- No automated CI configured
- Manual validation:
  - Backend: `python -m unittest discover -s tests -v` (from `backend/`)
  - Frontend: `npm run lint && npm run build` (from `frontend/`)

## Environment Configuration

**Required env vars (at least one LLM provider):**
- `GEMINI_API_KEY` - Google Cloud API key (recommended for responder)
- `GROQ_API_KEY` - Groq API key (recommended for suggester)
- `GITHUB_MODELS_TOKEN` + `GITHUB_MODELS_MODEL` - GitHub Models fallback

**Optional env vars:**
- `TAVILY_API_KEY` - Web search (recommended for web_search tool)
- `RESPONDER_PROVIDER=gemini` - Provider preference for agent answers (default: gemini)
- `SUGGESTER_PROVIDER=groq` - Provider preference for prompt suggestions (default: groq)
- `VITE_API_URL=http://localhost:8000` - Frontend API endpoint (default: /api)
- `VITE_AGENT_MOCK=true` - Run frontend without backend
- `REACT_AGENT_SKIP_DOTENV=1` - Skip loading `.env` file
- `REACT_AGENT_DISABLE_WEB_SEARCH_GATE=1` - Disable forced web_search for current-fact queries (tests use this)
- `PYTHON_EXECUTOR_TIMEOUT_SECONDS=30` - Subprocess sandbox timeout (range: 1–60, default: 30)

**Secrets location:**
- `backend/.env` - Not committed; copy from `.env.example`
- All env vars with KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL in the name are auto-redacted from logs

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints

**Outgoing:**
- None - No external callbacks or notifications

## Tool Definitions

**Tools available to the agent:**

**1. web_search**
- Purpose: Fetch current facts and external information
- Implementation: `backend/agent/tools.py` - `web_search()` function
- Provider: Tavily API via `tavily-python`
- Input: `query` (string)
- Output: Compact results with title, URL, snippet (max `TAVILY_SNIPPET_CHARS` chars)
- Gateway: In `backend/agent/graph.py` - `_requires_web_search()` uses regex patterns to force web_search for current-fact queries (max 2 per run)

**2. python_executor**
- Purpose: Run isolated Python code for multi-step computation
- Implementation: `backend/agent/tools.py` - `python_executor()` function
- Execution: Subprocess sandbox with:
  - AST validation of every node
  - Import whitelist: `math`, `json`, `re`, `statistics`, `random`, `itertools`, `functools`, `sys`, `sympy`, `numpy`
  - Blocked builtins: `open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `locals`, `vars`, `getattr`, `setattr`, `delattr`
  - Blocked attributes: `ctypes`, `path`, `__loader__`, etc. (prevent system access)
  - Timeout: `PYTHON_EXECUTOR_TIMEOUT_SECONDS` (default 30s, range 1–60s)
- Code normalization: Auto-strips Markdown fences, redundant safe imports
- Input: `code` (string)
- Output: stdout from subprocess

**3. calculator**
- Purpose: Evaluate exact arithmetic expressions
- Implementation: `backend/agent/tools.py` - `calculator()` function
- Execution: Direct `eval()` with AST validation, no builtins
- Allowed: Arithmetic operators, `math.*` module functions, constants
- Input: `expression` (string)
- Output: Numeric result

---

*Integration audit: 2026-06-29*
