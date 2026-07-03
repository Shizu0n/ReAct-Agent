---
phase: 05-mcp
plan: 03
subsystem: api
tags: [mcp, langgraph, tool-dispatch, discovery, langchain-mcp-adapters]

requires:
  - phase: 05-mcp
    provides: reachable /mcp/ route (Plan 05-02), fetch_url server (Plan 05-01)
provides:
  - discover_mcp_tools() — env-gated dynamic MCP discovery that degrades to ([], [])
  - tool_node MCP dispatch branch producing an identical Step (trace parity)
  - _filter_mcp_tools collision guard + build_graph mcp_tools/mcp_schemas threading
  - api.py lifespan discovery + handler threading
affects: [05-04]

tech-stack:
  added: []
  patterns: [env-gated-degrade-to-empty, pool-style-optional-threading, mcp-content-block-flattening, discovery-once-per-warm-instance]

key-files:
  created: [backend/agent/mcp_client.py]
  modified: [backend/agent/graph.py, backend/api.py, backend/tests/test_mcp.py, backend/tests/test_graph.py]

key-decisions:
  - "discover_mcp_tools() normalizes the configured URL to a trailing slash (the reachable endpoint is /mcp/)."
  - "tool_node flattens MCP content-block results ([{type:text,text:...}]) to plain text via _mcp_result_to_text — the adapter does NOT return a bare string, so the plan/research str(ainvoke(...)) would dump raw dicts into the trace."
  - "Collision guard drops MCP names colliding with native TOOLS AND memory_*/document_search (honors the plan's full prohibition list)."

patterns-established:
  - "Thread MCP tools through build_graph -> agent_node (merged schemas) + tool_node (dispatch map) exactly like pool; degrade to empty on unset/unreachable, never raise."

requirements-completed: [MCP-02, MCP-03, MCP-04]

coverage:
  - id: D1
    description: "discover_mcp_tools() is env-gated (unset -> ([],[]), zero I/O) and degrades to ([],[]) on unreachable/malformed without raising"
    requirement: "MCP-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_mcp.py::DiscoveryGateTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "A reachable server yields BaseTools + convert_to_openai_tool schemas; configured .../mcp is normalized to .../mcp/"
    requirement: "MCP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_mcp.py::DiscoveryTests"
        status: pass
      - kind: integration
        ref: "manual: real uvicorn + discover_mcp_tools() discovered fetch_url over the wire (verified this session)"
        status: pass
    human_judgment: false
  - id: D3
    description: "An MCP tool call produces a Step with the same six keys as a native call; content blocks flatten to text; errors become Error: observations; native tools cannot be shadowed"
    requirement: "MCP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_graph.py::McpToolNodeTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "SC1 live invoke + SC2 trace parity + SC3 unset-degrade against a deployed preview with a live LLM provider"
    requirement: "MCP-02, MCP-03, MCP-04"
    verification: []
    human_judgment: true
    rationale: "Requires a deployed /mcp/ route and a live LLM provider; cannot run in offline unit tests. See deploy-verify checklist."

duration: ~60min
completed: 2026-07-03
status: complete
---

# Phase 05 Plan 03: Agent as a dynamic MCP client

**The agent discovers the companion tool via `tools/list` at startup, invokes it inside the graph with trace parity, and degrades to zero MCP tools when `MCP_FETCH_SERVER_URL` is unset.**

## Performance
- **Duration:** ~60 min
- **Tasks:** 4 (3 implemented; 1 live checkpoint deferred to the user)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `backend/agent/mcp_client.py`: `discover_mcp_tools()` — env-gated, trailing-slash-normalizing, fresh `MultiServerMCPClient` with an explicit timeout, `convert_to_openai_tool` schemas; degrades to `([], [])` on unset (zero I/O) or any error (never raises).
- `backend/agent/graph.py`: `agent_node(extra_schemas=...)`, `tool_node` MCP dispatch branch (`await tool.ainvoke(full args)` + `_mcp_result_to_text` flattening), `_filter_mcp_tools` collision guard, `build_graph(mcp_tools=, mcp_schemas=)` threading.
- `backend/api.py`: lifespan discovers once (independent try/except), threads `app.state.mcp_tools/mcp_schemas` through `_run_agent`/`_stream_agent` and both route handlers.
- Tests: DiscoveryGateTests + DiscoveryTests (test_mcp) and McpToolNodeTests (test_graph). 8 new tests green.
- **Real round-trip verified this session:** a live uvicorn server + `discover_mcp_tools()` (URL configured without a trailing slash) discovered `fetch_url`, and `.ainvoke()` round-tripped a blocked-host `Error:` string end-to-end.

## Task Commits
Not committed — per user instruction. Changes staged for manual review.

## Files Created/Modified
- `backend/agent/mcp_client.py` (new) — discover_mcp_tools().
- `backend/agent/graph.py` — agent_node/tool_node/build_graph + _filter_mcp_tools + _mcp_result_to_text.
- `backend/api.py` — lifespan discovery + handler threading.
- `backend/tests/test_mcp.py`, `backend/tests/test_graph.py` — new test classes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Correctness — trace parity] MCP results are content-block lists, not strings**
- **Found during:** Task 1/2, real round-trip verification.
- **Issue:** langchain-mcp-adapters tools use `response_format="content_and_artifact"`; `.ainvoke()` returns `[{'type':'text','text':...,'id':...}]`. The plan/research `observation = str(await tool.ainvoke(...))` would render that raw list in the trace, breaking SC2. Mocks returning plain strings would not have caught this.
- **Fix:** Added `_mcp_result_to_text()` — extracts and joins the text blocks (str/list/fallback). `test_mcp_content_blocks_flattened_to_text` locks the behavior.

**2. [Correctness] Trailing-slash URL normalization in discover_mcp_tools()**
- **Issue:** The reachable endpoint is `/mcp/` (see 05-02); a URL configured as `.../mcp` would 405.
- **Fix:** Normalize to a trailing slash before constructing the client. `test_trailing_slash_added_to_configured_url` + the real round-trip confirm it.

**3. [Hardening] Collision guard broadened beyond TOOLS**
- **Fix:** `_filter_mcp_tools` drops names in `TOOLS` PLUS `memory_read/memory_write/document_search` — honoring the plan's prohibition ("...can never shadow calculator/web_search/python_executor/memory_*/document_search").

---
**Total deviations:** 3 (2 correctness, 1 hardening). No scope creep.

## Issues Encountered
The content-block return shape (deviation 1) was the key finding; caught by exercising the real client rather than mocks.

## Not Implemented (flagged for user)
- **Research Pattern 4** (union discovered MCP tool names into `/health` and `/config`) was NOT in the plan's tasks and is NOT implemented. Consequence: `fetch_url` will not appear in `/config` (the About-page tool list) even when MCP is enabled. Low-risk, legibility-only follow-up — recommend a small `/health` + `/config` change in a future slice if the About page should list MCP tools.

## User Setup Required
**Live SC1/SC2/SC3 (Task 4) is deferred to you** — needs a deployed `/mcp/` route + a live LLM provider. See the deploy-verify checklist.

## Next Phase Readiness
The agent discovers → invokes → traces an MCP tool end-to-end offline. Plan 05-04 documents it.

---
*Phase: 05-mcp*
*Completed: 2026-07-03*
