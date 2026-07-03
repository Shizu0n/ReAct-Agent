---
phase: 04-observability
plan: 03
subsystem: run-history-ui
tags: [react, hook, run-history, reasoning-panel-reuse, session-scoped, fallback-display, obs-05-verify]

# Dependency graph
requires:
  - phase: 04-observability
    plan: 02
    provides: "GET /runs -> { runs: RunListItem[] }; GET /trace/{id} -> AgentResponse (X-Session-Id scoped)"
  - phase: 04-observability
    plan: 01
    provides: "per-step elapsed_ms; usage.fallback_events ({provider, error}[])"
  - phase: 01-foundation
    provides: "ReasoningPanel step rendering; EvalsSection evalsUrl() base-URL + on-mount fetch/cancel pattern; useAgent sessionId"
provides:
  - "frontend/src/types/index.ts — FallbackEvent, Usage.fallback_events?, RunListItem, RunListResponse"
  - "frontend/src/hooks/useRunHistory.ts — session-scoped /runs + /trace fetch, loading/ready/empty/error states, never throws"
  - "frontend/src/components/RunHistory.tsx — list + detail, provider chip + fallback badge, per-step elapsed_ms trace"
  - "App History tab (nav item + render branch) passing sessionId from useAgent"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Session-scoped fetch: every /runs and /trace request sends the X-Session-Id header so history is the current session's only"
    - "On-mount fetch + cancelled-flag cleanup (mirrors EvalsSection); the hook swallows non-ok responses and JSON errors and maps them to an 'error' state — never throws to the component"
    - "Effect hygiene: all setState lives inside the async load() function, never synchronously in the effect body (satisfies react-hooks/set-state-in-effect)"
    - "Reuse over reinvention: trace detail renders steps in ReasoningPanel's visual language + CSS-variable design tokens rather than a new timeline framework"

key-files:
  created:
    - frontend/src/hooks/useRunHistory.ts
    - frontend/src/components/RunHistory.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/App.tsx

key-decisions:
  - "History placed between Chat and About in navItems; ActiveTab derives from navItems so the union widened automatically (no separate type edit)"
  - "Render branch is a nested ternary (chat -> ChatWorkspace, history -> RunHistory, else -> PortfolioView), matching the file's existing ternary style"
  - "OBS-05 satisfied by verification only — PortfolioView still mounts EvalsSection and was left unmodified"

requirements-completed: [OBS-02, OBS-03, OBS-04, OBS-05]

coverage:
  - id: T1
    description: "History tab renders a session-scoped list (timestamp/query/status/elapsed/provider/fallback); empty + error states are legible, no crash"
    requirement: OBS-02
    verification:
      - kind: build
        ref: "tsc -b && vite build (exit 0); useRunHistory sends X-Session-Id; list/empty/error states in RunHistory.tsx"
        status: pass
  - id: T2
    description: "Selecting a run loads its full trace and renders each step's per-step elapsed_ms"
    requirement: OBS-03
    verification:
      - kind: build
        ref: "RunHistory detail consumes GET /trace AgentResponse steps (elapsed_ms) via ReasoningPanel-style rendering"
        status: pass
  - id: T3
    description: "Provider used + fallback events ('{provider} failed -> ...') shown in list and/or detail"
    requirement: OBS-04
    verification:
      - kind: build
        ref: "RunListItem.provider chip + has_fallback badge; detail renders usage.fallback_events"
        status: pass
  - id: T4
    description: "EvalsSection still fetches + renders the committed baseline on the About tab"
    requirement: OBS-05
    verification:
      - kind: manual
        ref: "PortfolioView.tsx unmodified; still mounts EvalsSection (grep = 2 refs)"
        status: pass

# Metrics
duration: split (session-limited background agent + inline completion)
completed: 2026-07-02
status: complete
---

# Phase 4 Plan 03: Run-History Dashboard Summary

**A new "History" tab surfaces the session's persisted runs and, on click, each run's full reasoning trace — per-step timing and provider fallbacks — reusing ReasoningPanel's step rendering and the app's design tokens. Consumes 04-02's `/runs` + `/trace/{id}` endpoints; no backend change. The About-tab eval panel (OBS-05) is confirmed intact.**

## Accomplishments
- `frontend/src/types/index.ts`: added `FallbackEvent { provider; error }`, `Usage.fallback_events?: FallbackEvent[]`, `RunListItem` (run_id, query, status, elapsed_ms, created_at, provider, has_fallback), and `RunListResponse`.
- `frontend/src/hooks/useRunHistory.ts` (new): `apiBase()` mirroring EvalsSection's base-URL logic; on-mount/`refresh()` fetch of `/runs` with `X-Session-Id` into loading/ready/empty/error; `selectRun(id)` fetches `/trace/{id}` into an `AgentResponse` with a request-token guard against stale detail responses; guards non-ok/JSON errors and never throws.
- `frontend/src/components/RunHistory.tsx` (new): list (timestamp/query/status/elapsed + provider chip + fallback badge) with legible loading/empty/error states, and a detail pane that renders the trace steps (per-step `elapsed_ms`) plus a provider-fallback section, in ReasoningPanel's visual language.
- `frontend/src/App.tsx`: imported `History` (lucide) + `RunHistory`; added the `history` nav item (Chat → History → About); added the `activeTab === 'history'` render branch passing `sessionId`.
- OBS-05: verified `PortfolioView` still mounts `EvalsSection` (no code change).

## Verification
- `npm run build` (`tsc -b && vite build`) → **built successfully (exit 0)** — full typecheck + bundle passes with the new hook/component/wiring.
- `npx eslint` scoped to the four Phase-4 files (`useRunHistory.ts`, `RunHistory.tsx`, `App.tsx`, `types/index.ts`) → **clean (exit 0)**.
- Manual QA (no frontend test framework) deferred to the user: run a Chat query → open History → the run appears; click it → full step trace with per-step `elapsed_ms`; About → eval baseline still renders; empty session → legible empty state.

## Task Commits
Per project git policy the USER commits manually — this run made ZERO commits and staged nothing. All changes are uncommitted working-tree edits.

## Deviations / Notes (flagged for user review)
1. **Fixed one `react-hooks/set-state-in-effect` lint error in the new `useRunHistory.ts`** (the background agent's version called `setState` synchronously in the effect body for the `!sessionId` branch). Moved all `setState` into the async `load()` so the effect body has none directly — behavior unchanged.
2. **Pre-existing, out-of-scope lint failure left as-is:** `frontend/src/hooks/useDocuments.ts` (Phase 3 RAG) has a `react-hooks/set-state-in-effect` error on `void listDocuments()`. It is **unmodified vs HEAD `55a00a2`** — it predates Phase 4 and is unrelated to this plan. Per surgical-changes policy it was NOT touched. It does not block `npm run build`. It does make a whole-repo `npm run lint` non-zero. Recommend a separate one-line fix (same pattern as #1) if a clean `npm run lint` is desired.
3. **Execution note (non-code):** the background agent that built the types/hook/component was cut off by a session limit before wiring `App.tsx` or writing this summary; the orchestrator completed the App wiring + the lint fix inline and verified the build.

## User Setup Required
None. The History tab reads live from `/runs` + `/trace`; with no persisted runs it shows the empty state.

---
*Phase: 04-observability* · *Completed: 2026-07-02*
