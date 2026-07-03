---
phase: 05-mcp
plan: 04
subsystem: docs
tags: [readme, mcp, documentation, mermaid]

requires:
  - phase: 05-mcp
    provides: implemented MCP integration (Plans 05-01/02/03)
provides:
  - README ## MCP section (prose + mermaid diagram + MCP_FETCH_SERVER_URL toggle)
  - MCP_FETCH_SERVER_URL entry in the README Environment .env block
affects: []

tech-stack:
  added: []
  patterns: [readme-section-mirrors-existing-diagram-palette]

key-files:
  created: []
  modified: [README.md]

key-decisions:
  - "Placed ## MCP after ## Tools; mermaid diagram reuses the existing Diagram section's color palette; documented the /mcp/ trailing-slash requirement."

patterns-established: []

requirements-completed: [MCP-05]

coverage:
  - id: D1
    description: "README ## MCP section documents agent-as-MCP-client, fetch_url, tools/list discovery, trace parity, a flow diagram, and the MCP_FETCH_SERVER_URL toggle + graceful degradation; env var added to the .env block"
    requirement: "MCP-05"
    verification:
      - kind: automated
        ref: "grep -q '^## MCP' && grep -q MCP_FETCH_SERVER_URL && grep -qi fetch_url && grep -q MultiServerMCPClient README.md -> PASS"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-07-03
status: complete
---

# Phase 05 Plan 04: Document the MCP architecture

**A `## MCP` README section — prose, a palette-matched mermaid flow diagram (agent ↔ MultiServerMCPClient ↔ Streamable HTTP ↔ /mcp FastMCP ↔ fetch_url), and the `MCP_FETCH_SERVER_URL` off-switch — legible to a recruiter in minutes.**

## Performance
- **Duration:** ~10 min
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- `README.md` `## MCP` section: agent-as-its-own-MCP-client over Streamable HTTP into the same Vercel Function; `fetch_url` (SSRF/DoS/injection-hardened); `discover_mcp_tools` `tools/list` discovery; trace parity (same `Step`, no frontend change); mermaid diagram reusing the existing palette; `MCP_FETCH_SERVER_URL` toggle + graceful degradation + the `/mcp/` trailing-slash note.
- `MCP_FETCH_SERVER_URL=` added to the Environment `.env` block with an optional/off-switch comment.

## Task Commits
Not committed — per user instruction.

## Files Created/Modified
- `README.md` — `## MCP` section + `MCP_FETCH_SERVER_URL` env entry.

## Decisions Made
- Documented `/mcp/` (trailing slash) as the configured value, consistent with the Plan 05-02/05-03 findings, so the docs never contradict the implemented behavior.

## Deviations from Plan
None — docs-only, executed as written.

## Issues Encountered
None.

## User Setup Required
None (docs only).

## Next Phase Readiness
Phase 5 (MCP) implementation and documentation complete offline. Remaining: the three live/deploy human-verify checkpoints (see the deploy-verify checklist) and the user commit.

---
*Phase: 05-mcp*
*Completed: 2026-07-03*
