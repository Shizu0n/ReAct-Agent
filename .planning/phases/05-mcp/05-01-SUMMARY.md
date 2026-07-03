---
phase: 05-mcp
plan: 01
subsystem: api
tags: [mcp, fastmcp, httpx, ssrf, tools]

requires:
  - phase: 01-foundation
    provides: tool convention (error-string-not-raise, _env_int caps), SYSTEM_PROMPT untrusted-content barriers
provides:
  - FastMCP companion server (mcp_server) with stateless_http + mounting-safe streamable_http_path="/"
  - fetch_url MCP tool, hardened against SSRF / DoS / prompt injection
  - MCP dependency pins recorded in both requirements files
  - SYSTEM_PROMPT FETCHED PAGE untrusted-content barrier
affects: [05-02, 05-03, 05-04]

tech-stack:
  added: [langchain-mcp-adapters>=0.3.0,<0.4.0, mcp>=1.28.0,<2.0.0]
  patterns: [FastMCP-mount-safe-construction, SSRF-host-resolution-guard, delimiter-wrapped-untrusted-output]

key-files:
  created: [backend/agent/mcp_server.py, backend/tests/test_mcp.py]
  modified: [backend/requirements.txt, api/requirements.txt, backend/agent/prompts.py]

key-decisions:
  - "Packages were already installed at the exact pinned versions (mcp==1.28.1, langchain-mcp-adapters==0.3.0); the legitimacy gate reduced to recording pins — no unreviewed install."
  - "SSRF guard resolves the host via socket.getaddrinfo and rejects ANY private/loopback/link-local/reserved/multicast/unspecified address, fails closed on resolution error, and re-checks the host after redirects."
  - "True byte cap on response.content (not response.text) before decoding."

patterns-established:
  - "MCP tool = @mcp_server.tool() returning a delimiter-wrapped, char-capped string, Error: on every failure path, never raises."

requirements-completed: [MCP-01]

coverage:
  - id: D1
    description: "fetch_url extracts readable text, wraps it in FETCHED PAGE delimiters, caps bytes/chars, and returns Error: strings instead of raising"
    requirement: "MCP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_mcp.py::FetchToolTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "fetch_url blocks non-http(s) schemes and internal/private/loopback/link-local hosts with no outbound GET (SSRF)"
    requirement: "MCP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_mcp.py::FetchToolTests::test_internal_hosts_blocked_without_request"
        status: pass
    human_judgment: false
  - id: D3
    description: "FastMCP server exposes fetch_url and a callable ASGI app; SYSTEM_PROMPT gains the FETCHED PAGE barrier"
    requirement: "MCP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_mcp.py::ServerMountTests"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-07-03
status: complete
---

# Phase 05 Plan 01: Companion MCP server + fetch_url

**A FastMCP companion server exposing one real, SSRF/DoS/injection-hardened `fetch_url` tool, with the two MCP dependency pins recorded in both requirements files.**

## Performance
- **Duration:** ~40 min
- **Tasks:** 3 (1 gate resolved, 2 implemented)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `backend/agent/mcp_server.py`: `mcp_server = FastMCP(stateless_http=True, json_response=True, streamable_http_path="/")` + `fetch_url` with an HTML text extractor, SSRF host-resolution guard, byte/char caps, redirect re-check, and `strip_invisible` zero-width stripping.
- `SYSTEM_PROMPT` gained the fetch_url call bullet + the FETCHED PAGE untrusted-content barrier (mirrors RETRIEVED DOCUMENTS / USER MEMORIES).
- Recorded `langchain-mcp-adapters>=0.3.0,<0.4.0` and `mcp>=1.28.0,<2.0.0` in `backend/requirements.txt` (UTF-16 LE+BOM+CRLF preserved) and `api/requirements.txt` (Vercel deploy source).
- `backend/tests/test_mcp.py`: FetchToolTests (extraction, truncation, non-HTML, every SSRF-blocked range, unresolvable-host fail-closed, redirect-to-internal block, HTTP-exception→Error) + ServerMountTests. 11 tests green.

## Task Commits
Not committed — per user instruction ("do not commit, just implement"). All changes are staged in the working tree for manual review. Suggested commit name at the end of the phase report.

## Files Created/Modified
- `backend/agent/mcp_server.py` (new) — FastMCP server + fetch_url.
- `backend/tests/test_mcp.py` (new) — FetchToolTests + ServerMountTests.
- `backend/agent/prompts.py` — FETCHED PAGE bullets.
- `backend/requirements.txt`, `api/requirements.txt` — two MCP pins.

## Decisions Made
- The blocking package-legitimacy gate was already satisfied in fact (packages installed at the exact pins, official SDKs, imports verified) — recorded the pins rather than performing an unreviewed install.
- Byte cap applied to `response.content` (not `.text`) for a genuine byte bound.

## Deviations from Plan
Note: the FastMCP construction also disables DNS-rebinding protection (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`). This was NOT in the plan/research example; it was found necessary during Plan 05-02's in-process smoke (the default rejects every Host header — including the Vercel domain — with HTTP 421). Full rationale is recorded in 05-02-SUMMARY.md.

## Issues Encountered
None during this plan's scope.

## User Setup Required
None for this plan. `MCP_FETCH_SERVER_URL` is configured in Plan 05-02/05-03.

## Next Phase Readiness
The tool exists and is unit-safe. Plan 05-02 mounts it over HTTP.

---
*Phase: 05-mcp*
*Completed: 2026-07-03*
