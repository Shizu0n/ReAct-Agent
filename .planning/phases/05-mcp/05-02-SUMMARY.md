---
phase: 05-mcp
plan: 02
subsystem: api
tags: [mcp, fastapi, mount, vercel, lifespan, dns-rebinding]

requires:
  - phase: 05-mcp
    provides: mcp_server (FastMCP) + fetch_url (Plan 05-01)
provides:
  - /mcp route mounted into the existing FastAPI app before the SPA catch-all
  - combined AsyncExitStack lifespan running mcp_server.session_manager.run() independently of the DB pool
  - vercel.json /mcp rewrites
  - DNS-rebinding-protection disabled so the deployed Host is not rejected (421 fix)
affects: [05-03, 05-04]

tech-stack:
  added: []
  patterns: [asyncexitstack-combined-lifespan, mount-before-spa-catchall, in-process-asgi-smoke-as-deploy-proxy]

key-files:
  created: []
  modified: [backend/api.py, vercel.json, backend/agent/mcp_server.py, backend/tests/test_mcp.py]

key-decisions:
  - "Disabled DNS-rebinding protection on the FastMCP server — its default (on, empty allow-list) rejects EVERY Host header (including the Vercel domain) with HTTP 421."
  - "The reachable endpoint is /mcp/ (trailing slash); bare /mcp is shadowed by the SPA catch-all. Added a bare /mcp vercel rewrite too and documented the trailing-slash requirement."
  - "Added an in-process ASGI JSON-RPC smoke test as an offline proxy for the A2 deploy checkpoint (stronger than a route-order-only check)."

patterns-established:
  - "Mount an ASGI sub-app before the /{path:path} catch-all and run its session manager via the parent lifespan's AsyncExitStack."

requirements-completed: [MCP-01]

coverage:
  - id: D1
    description: "/mcp mounted before the SPA catch-all; combined lifespan runs the MCP session manager independently of the DB pool"
    requirement: "MCP-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_mcp.py::ServerReachabilityTests::test_mount_precedes_spa_catchall"
        status: pass
    human_judgment: false
  - id: D2
    description: "The mounted /mcp/ route answers a JSON-RPC initialize with 200 + result in-process (offline proxy for the deploy smoke)"
    requirement: "MCP-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_mcp.py::ServerReachabilityTests::test_mcp_endpoint_answers_jsonrpc_in_process"
        status: pass
    human_judgment: false
  - id: D3
    description: "A2 cross-instance deploy smoke — /mcp/ answers tools/list on two spaced requests against a real Vercel preview"
    requirement: "MCP-01"
    verification: []
    human_judgment: true
    rationale: "Requires a live Vercel deploy + curl; serverless cross-instance behavior cannot be exercised offline. See deploy-verify checklist."

duration: ~50min
completed: 2026-07-03
status: complete
---

# Phase 05 Plan 02: Mount /mcp + de-risk serverless reachability

**The companion MCP server is mounted at `/mcp` inside the same FastAPI app via an AsyncExitStack lifespan, with two live-deploy blockers (Host-header 421, trailing-slash shadowing) found and fixed offline.**

## Performance
- **Duration:** ~50 min
- **Tasks:** 2 (1 implemented; 1 deploy checkpoint deferred to the user)
- **Files modified:** 4

## Accomplishments
- `backend/api.py`: `app.mount("/mcp", mcp_server.streamable_http_app())` registered after middleware and before the `serve_frontend` catch-all; lifespan rewritten to `async with AsyncExitStack()` entering `mcp_server.session_manager.run()`, kept independent of the DB-pool try/except (Pitfall 4).
- `vercel.json`: `/mcp/:path*` and bare `/mcp` rewrites to `/api/index.py`.
- Offline tests: route-order guard + in-process JSON-RPC `initialize` smoke (200 + result).

## Task Commits
Not committed — per user instruction. Changes staged for manual review.

## Files Created/Modified
- `backend/api.py` — mount + AsyncExitStack lifespan.
- `vercel.json` — /mcp rewrites.
- `backend/agent/mcp_server.py` — `transport_security` (DNS-rebinding disabled).
- `backend/tests/test_mcp.py` — ServerReachabilityTests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Correctness — deploy blocker] DNS-rebinding protection rejected every Host (HTTP 421)**
- **Found during:** Task 2 offline smoke (`POST /mcp/` → 421 "Invalid Host header").
- **Issue:** `FastMCP` defaults `enable_dns_rebinding_protection=True` with an empty `allowed_hosts`, so every request (including the deployed Vercel domain) is rejected. The plan/research FastMCP example omitted this.
- **Fix:** Constructed with `TransportSecuritySettings(enable_dns_rebinding_protection=False)` in `mcp_server.py`. Justified: the server is public, stateless, and exposes only a read-only, SSRF-hardened tool — rebinding protection guards nothing here and would block the agent from calling its own domain.
- **Verification:** In-process `POST /mcp/` initialize now returns 200 + JSON-RPC result.

**2. [Correctness — deploy blocker] Bare /mcp shadowed by the SPA catch-all**
- **Found during:** Task 2 offline smoke (`GET /mcp` → SPA HTML; `POST /mcp` → 405).
- **Issue:** Starlette's `Mount("/mcp")` matches only `/mcp/...`; the greedy `/{path:path}` catch-all intercepts bare `/mcp` before `redirect_slashes` can redirect. The reachable endpoint is `/mcp/` (trailing slash).
- **Fix:** Documented `/mcp/`; added a bare `/mcp` vercel rewrite; Plan 05-03's `discover_mcp_tools` normalizes the configured URL to a trailing slash.
- **Verification:** `POST /mcp/` → 200; the real client round-trip (Plan 05-03) confirmed discovery works with a URL configured as `.../mcp`.

**3. [Test strength] Added an in-process ASGI smoke beyond the plan's route-order check**
- **Fix:** `ServerReachabilityTests` runs the app lifespan and POSTs a JSON-RPC initialize — a genuine offline proxy for the deploy checkpoint (user-approved "offline proxies").

---
**Total deviations:** 3 (2 necessary deploy-blocker fixes, 1 test strengthening). No scope creep.

## Issues Encountered
See deviations — both live-deploy blockers were caught offline via the in-process smoke.

## User Setup Required
**Deploy smoke (Task 2) is deferred to you.** Deploy a preview, set `MCP_FETCH_SERVER_URL` to `<preview>/mcp/`, and POST a `tools/list` to `<preview>/mcp/` twice (30–60s apart). See the deploy-verify checklist.

## Next Phase Readiness
`/mcp/` is reachable in-process and the two most likely deploy failures are already fixed. Plan 05-03 wires the agent as a client.

---
*Phase: 05-mcp*
*Completed: 2026-07-03*
