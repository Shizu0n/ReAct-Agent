# Codebase Concerns

**Analysis Date:** 2026-06-29

## Tech Debt

**Python Version Incompatibility:**
- Issue: Dependencies pinned to Python ≤3.13. `numpy 1.26.4` has no Python 3.14 wheel and fails to build from source.
- Files: `requirements.txt`, `CLAUDE.md` (line 12)
- Impact: Cannot upgrade Python beyond 3.13 without rebuilding numpy from source, which is time-consuming and may fail.
- Fix approach: Upgrade `numpy` in `requirements.txt` to a version with Python 3.14+ wheels (e.g., `numpy >=1.27.0`), or constrain Python version in CI/Vercel build config.

**Documentation Timeout Inconsistency:**
- Issue: README.md line 131 states python_executor has "a 10s timeout", but `backend/agent/tools.py` line 18 has `DEFAULT_PYTHON_EXECUTOR_TIMEOUT_SECONDS = 30`. CLAUDE.md correctly documents 30s.
- Files: `README.md`, `backend/agent/tools.py`
- Impact: Confuses developers about actual limits and could lead to assumptions about execution time.
- Fix approach: Update README.md line 131 to state "30s timeout" and remove "10s" reference entirely.

**Dual API Entrypoints:**
- Issue: Same FastAPI app defined in `backend/api.py` and re-exported through `api/index.py`. Both need to stay in sync.
- Files: `backend/api.py`, `api/index.py`, `vercel.json`
- Impact: Risk of drift if one is updated without the other. Every new endpoint requires decorators on both routes.
- Fix approach: Consider consolidating to a single entrypoint or document the sync requirement in CLAUDE.md more prominently.

## Known Bugs

**Web Search URL Extraction Misses Edge Cases:**
- Symptoms: Source URLs may not be appended to answers if the regex fails or captures malformed URLs.
- Files: `backend/agent/graph.py` lines 143, 223-225
- Trigger: Complex URL patterns with query params, fragments, or special characters; URLs with Unicode characters.
- Workaround: Manually cite sources in follow-up query.

**Blank Provider Responses Not Caught Early:**
- Symptoms: If a provider returns HTTP 200 with no content and no tool calls (e.g., Gemini under quota pressure), the agent treats it as a provider failure and falls back instead of returning empty content to user.
- Files: `backend/agent/llms.py` lines 319-328
- Impact: User sees "All free model providers failed" instead of actual response attempt details.
- Current behavior: Intentional (raises RuntimeError to trigger fallback), but the error message could be clearer.

## Security Considerations

**Python Executor Safe Wrapper is Fragile:**
- Risk: Monkey-patching `builtins` at runtime (lines 341-355 in `backend/agent/tools.py`) is complex and may have edge cases. Malicious code could potentially bypass restrictions through `__getattribute__`, `__class__`, or direct C extension calls.
- Files: `backend/agent/tools.py` lines 282-356
- Current mitigation: AST validation before execution + import whitelist + runtime wrapper. Subprocess isolation provides defense-in-depth.
- Recommendations: 
  1. Add audit/security tests for known sandbox-escape techniques (e.g., `().__class__.__bases__[0].__subclasses__()`)
  2. Consider using `RestrictedPython` library as an additional layer if security requirements are strict.
  3. Document that this is "sandbox-like" not "fully isolated" — subprocess provides real isolation but the runtime wrapper is not cryptographically secure.

**Exception Messages Leaked to Clients:**
- Risk: Streaming responses in `backend/api.py` line 319 emit exception messages directly to SSE payloads, potentially leaking internal state or API details.
- Files: `backend/api.py` lines 315-326
- Impact: Client sees full exception details including provider names, API errors, and internal function names.
- Recommendations: 
  1. Log full exception server-side.
  2. Send generic user-facing error message to client ("Agent failed to process your request").
  3. Expose run_id for support/debugging.

**Tavily API Key Exposure:**
- Risk: Missing `TAVILY_API_KEY` returns plain error "TAVILY_API_KEY environment variable is not set" without guidance.
- Files: `backend/agent/tools.py` line 222
- Impact: User does not know how to resolve the issue (env var setup, optional feature, etc.).
- Recommendations: Enhance error message: "Web search is not configured. Set TAVILY_API_KEY to enable (optional feature)."

## Performance Bottlenecks

**Python Executor Timeout is Conservative:**
- Problem: 30s default timeout (line 357-362 in `backend/agent/tools.py`) is long and blocks the request thread. A hung or slow computation ties up resources.
- Files: `backend/agent/tools.py` line 357-362
- Cause: Timeout is user-configurable but high default allows expensive computations. Subprocess cleanup may be delayed if process is killed mid-execution.
- Improvement path: 
  1. Reduce default to 10s (matches common API timeouts).
  2. Add warning logs if execution approaches timeout (e.g., log at 80% elapsed).
  3. Consider async subprocess execution to avoid thread blocking.

**MAX_ITERATIONS = 10 May Be Too Aggressive:**
- Problem: Complex multi-step queries may hit the 10-iteration limit before completing, raising `MaxIterationsError`.
- Files: `backend/agent/graph.py` line 28, 379-380
- Cause: Each tool call + observation = 1 iteration. Web search + analysis + follow-up = 3+ iterations easily.
- Improvement path:
  1. Increase default to 15 or 20.
  2. Or make it configurable per-request via query parameter.
  3. Log iteration count at each step to help users understand when they're near the limit.

**MAX_CURRENT_FACT_WEB_SEARCHES = 2 Hard Limit:**
- Problem: If 2 web searches do not return sufficient results, the agent stops searching and returns incomplete answers.
- Files: `backend/agent/graph.py` line 142, 303-314
- Cause: Prevents search loops but may be too strict for complex fact-checking queries.
- Improvement path:
  1. Allow 3-4 searches for particularly fact-heavy queries.
  2. Or implement a smarter cutoff: if each search returns no new info (content similarity check), stop early.

**In-Memory Trace Storage:**
- Problem: `RUNS` dict in `backend/api.py` (line 80) stores last 100 runs in memory. On server restart, all traces are lost. At high traffic, memory usage grows.
- Files: `backend/api.py` lines 80-82, 147-154
- Cause: No persistence layer (database). Only the in-memory deque tracks order.
- Improvement path:
  1. Add SQLite or Redis backing for trace persistence.
  2. Or document that traces are ephemeral and should not be relied upon for long-term audit.
  3. Implement trace export (e.g., `/export-trace/{run_id}`) so users can save important runs.

## Fragile Areas

**Web Search Guardrail Regex Patterns:**
- Files: `backend/agent/graph.py` lines 117-140
- Why fragile: Regex patterns are hardcoded and may miss variations:
  - "what's the latest…" (contraction not matched by `\bis\s+`)
  - "How recent is…" (different phrasing for recency)
  - Queries in other languages or with typos
- Safe modification: Add a test suite (`test_graph.py`) with 20+ edge-case queries to validate `_requires_web_search()`. Ensure both false positives (queries forced to web_search) and false negatives (queries that should search but don't) are measured.
- Test coverage: Currently not visible in `backend/tests/`.

**SSE Streaming Buffer Handling (Frontend):**
- Files: `frontend/src/hooks/useAgent.ts` lines 330-347, 557-587
- Why fragile: Manual SSE buffer parsing without EventSource API. Handles partial flushes and Vercel edge proxying, but edge cases:
  - Malformed JSON in payload could throw uncaught error
  - Very large payloads might exceed buffer size
  - Network drops mid-payload leave incomplete buffer
- Safe modification: 
  1. Wrap `JSON.parse(data)` in try/catch at line 574.
  2. Add buffer size limit check.
  3. Add test cases for malformed/partial data.
- Test coverage: No frontend tests visible.

**Two-Level Dispatcher Route Registration:**
- Files: `backend/api.py` (every route), `vercel.json` lines 24-31
- Why fragile: Each endpoint must be registered twice (`/run` and `/api/run`). Easy to forget one when adding new endpoints.
- Safe modification: Add a helper that auto-registers both routes, or document the pattern prominently in CLAUDE.md before each route definition.

## Scaling Limits

**In-Memory Run Storage Max 100:**
- Current capacity: Last 100 runs stored in `RUNS` dict.
- Limit: On server restart, all data lost. No trace persistence.
- Scaling path: 
  1. Implement persistent trace store (SQLite, PostgreSQL, or Cloud Firestore).
  2. Or increase to 1000 and implement LRU eviction with disk spillover.

**Single Python Executor Process Per Request:**
- Current capacity: One subprocess spawned per `python_executor` call. Timeout is 30s.
- Limit: At high concurrency, many subprocesses could consume memory/CPU. No process pooling.
- Scaling path:
  1. Implement process pool (e.g., `concurrent.futures.ProcessPoolExecutor`) to reuse processes.
  2. Or use a queue-based system (Celery) for long-running code execution.

**Frontend Local Storage Limit:**
- Current capacity: `localStorage` in browser (~5-10MB per domain).
- Limit: Large chat histories (100+ messages, 500+ steps) could exceed quota, causing silent failures.
- Scaling path:
  1. Implement IndexedDB for larger storage.
  2. Or compress old sessions before storing.
  3. Or archive old sessions to backend.

## Dependencies at Risk

**Pinned Versions May Diverge:**
- Risk: `requirements.txt` has pinned exact versions (e.g., `fastapi==0.115.4`). No upstream security patches without manual intervention.
- Files: `requirements.txt`
- Impact: Security vulnerabilities in dependencies not auto-patched. Outdated packages may drop free-tier APIs or change behavior.
- Migration plan:
  1. Switch to tilde constraints: `fastapi~=0.115.4` (allows patch updates).
  2. Or use a lock file (Poetry, pip-compile) with periodic dependency update PRs.
  3. Monitor CVE feeds for each dependency.

**LangGraph/LangChain Pinned to Specific Versions:**
- Risk: `langgraph==0.2.45` is pinned. Future versions may change the `StateGraph` API.
- Files: `requirements.txt`
- Impact: Eventually must upgrade or fork; no smooth migration path.
- Monitoring: Watch LangGraph changelog for breaking changes. Test major version upgrades in a branch before committing.

## Missing Critical Features

**No Trace Persistence:**
- Problem: Run traces stored only in memory. Lost on server restart.
- Blocks: Audit trail, compliance, debugging, user-facing "history" for long-lived sessions.
- Priority: Medium (low if ephemeral by design, high if claimed to persist).

**No Rate Limit per User/Session:**
- Problem: Rate limiting is per IP (`slowapi`), not per user. One IP can still flood with requests if running locally or behind proxy.
- Blocks: Multi-user SaaS deployments, shared office networks.
- Priority: Low for portfolio project, high if deployed as service.

**No Conversation/Session Persistence on Backend:**
- Problem: Frontend persists chat in localStorage, but backend has no session concept. Each run is independent.
- Blocks: Resuming conversations across devices, server-side session management.
- Priority: Low for current architecture, high if multi-device support needed.

**No Fallback Web Search Provider:**
- Problem: Only Tavily supported. If Tavily API is down or quota exhausted, web_search fails.
- Blocks: Resilience in production.
- Priority: Medium.

## Test Coverage Gaps

**Frontend Testing Absent:**
- What's not tested: React components (ChatWorkspace, ReasoningPanel, etc.), useAgent hook state transitions, SSE parsing, localStorage persistence.
- Files: `frontend/src/` (no test files found)
- Risk: UI regressions, state management bugs, localStorage failures silent until deployed.
- Priority: High for production, low for portfolio.

**Streaming Error Scenarios:**
- What's not tested: Network interruption mid-stream, malformed SSE payloads, provider timeouts during streaming.
- Files: `backend/api.py` lines 249-340 (no visible tests)
- Risk: Streaming failures may leave UI in incomplete state.
- Priority: High — add test cases for:
  1. Provider returning empty response mid-stream
  2. Tool execution timeout
  3. Malformed tool output

**Rate Limiting Behavior:**
- What's not tested: Exceeding 10/min limit, concurrent requests from same IP, exemption of `/suggestions`.
- Files: `backend/api.py` lines 86-97 (no visible tests)
- Risk: Limit may not work as intended under load.
- Priority: Medium.

**Tavily API Failures:**
- What's not tested: API down, rate limited, malformed response, timeout.
- Files: `backend/agent/tools.py` lines 205-245 (no visible error case tests)
- Risk: web_search failures not handled gracefully.
- Priority: Medium.

**Web Search Guardrail Patterns:**
- What's not tested: Edge cases for `_requires_web_search()`, `_is_source_followup()`, `_web_search_action_input()`.
- Files: `backend/agent/graph.py` lines 171-193 (no visible tests)
- Risk: Guardrail may incorrectly force or skip web_search, regressing eval baseline.
- Priority: High — add parameterized tests with 20+ examples.

**Python Executor Sandbox Bypass Attempts:**
- What's not tested: Known escape techniques like `__class__`, `__bases__`, `__subclasses__`, ctypes import attempts.
- Files: `backend/agent/tools.py` (limited tests in `backend/tests/test_agent.py`)
- Risk: Undetected sandbox escape vulnerability.
- Priority: High for security-critical deployments.

---

*Concerns audit: 2026-06-29*
