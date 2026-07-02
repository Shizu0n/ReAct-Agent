---
phase: 03-rag
plan: 03
subsystem: frontend
tags: [react, hooks, upload, multipart, session]

# Dependency graph
requires:
  - phase: 03-02
    provides: POST /upload, GET /documents/{session_id}
  - phase: 02-memory
    provides: getOrCreateSessionId + sessionId prop threaded through useAgent -> ChatWorkspace
provides:
  - frontend/src/hooks/useDocuments.ts — uploadDocument + listDocuments, reuses the useAgent session id
  - frontend/src/components/demo/DocumentPanel.tsx — file picker + in-flight indicator + inline error + per-session list
  - DocumentInfo / UploadResult / DocumentState types
  - <DocumentPanel sessionId={sessionId} /> mounted in ChatWorkspace
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Multipart upload from the browser: FormData with no explicit Content-Type (browser sets the boundary)"
    - "Hook reuses the single localStorage session id (react-agent:session-id); never creates a second one"
    - "listDocuments/uploadDocument via useCallback so the mount useEffect has a stable dependency"

key-files:
  created:
    - frontend/src/hooks/useDocuments.ts
    - frontend/src/components/demo/DocumentPanel.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/components/ChatWorkspace.tsx

key-decisions:
  - "Local apiBaseUrl() copy in the hook (the one in useAgent is not exported) — same VITE_API_URL || '/api' logic"
  - "Concurrent uploads guarded (uploading flag); button disabled while ingesting"
  - "Upload errors read the JSON detail (413/415) and render inline; list fetch never throws (falls back to [])"

requirements-completed: [RAG-01, RAG-03, RAG-07]

coverage:
  - id: F1
    description: "Upload control picks a PDF/text file, shows an in-flight indicator, then the returned chunk count"
    requirement: RAG-03
    verification:
      - kind: build
        ref: "npm run build (tsc -b && vite build) passes — no type errors"
        status: pass
      - kind: manual
        ref: "browser: pick a file -> 'Ingesting...' -> 'Stored N chunks' — pending human verify"
        status: pending
  - id: F2
    description: "Per-session document list loads on mount and refreshes after each upload"
    requirement: RAG-07
    verification:
      - kind: build
        ref: "npm run build passes"
        status: pass
      - kind: manual
        ref: "browser: uploaded file appears with chunk count; persists on reload for same session — pending human verify"
        status: pending

# Metrics
duration: inline
completed: 2026-07-02
status: complete
---

# Phase 3 Plan 03: Document Upload Widget Summary

**The browser upload experience: a DocumentPanel in the chat workspace with a file picker, in-flight indicator, inline error, and a per-session filename + chunk-count list — reusing the existing session id.**

## Accomplishments
- `frontend/src/types/index.ts`: `DocumentInfo`, `UploadResult`, `DocumentState`.
- `frontend/src/hooks/useDocuments.ts`: `useDocuments(sessionId)` returning `{ documents, uploading, error, uploadDocument }`. `uploadDocument` posts multipart to `/upload` with the `x-session-id` header, surfaces 413/415 JSON `detail` inline, and refreshes the list on success; `listDocuments` fetches on mount and never throws.
- `frontend/src/components/demo/DocumentPanel.tsx`: hidden file input (`.pdf,.txt,.md,application/pdf,text/plain`) + labelled Upload button (disabled while ingesting), a "Stored N chunks" confirmation (with skipped count on truncation), inline error, and the per-session list with an empty state — all using the existing `var(--...)` design tokens and lucide icons.
- `ChatWorkspace.tsx`: `<DocumentPanel sessionId={sessionId} />` mounted just after the error banner, before the ChatPanel container. ChatPanel/App untouched.

## Verification
- `npm run build` (`tsc -b && vite build`) passes — TypeScript clean, production bundle built.
- Live upload UX (in-flight indicator, chunk-count confirmation, list persistence on reload) NOT exercised headlessly — human-verify in the live UI with the backend running.

## Task Commits
USER commits manually — NO commits made here; all edits uncommitted.

## Deviations from Plan
None. Followed the plan and PATTERNS analogs (ChatPanel styling, useAgent session-id reuse).

## User Setup Required
None new.

---
*Phase: 03-rag* · *Completed: 2026-07-02*
