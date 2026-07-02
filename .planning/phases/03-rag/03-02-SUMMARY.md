---
phase: 03-rag
plan: 02
subsystem: api
tags: [fastapi, upload, multipart, vercel, session-scoped]

# Dependency graph
requires:
  - phase: 03-01
    provides: agent.ingest.ingest_document
  - phase: 01-foundation
    provides: documents/document_chunks schema, app.state.pool
  - phase: 02-memory
    provides: _get_session_id / _is_valid_session_id, dual-route + vercel-rewrite convention
provides:
  - POST /upload + /api/upload — multipart ingest, 2 MB cap (413), type whitelist (415), pool guard (503)
  - GET /documents/{session_id} + /api/ variant — per-session filename + chunk_count list
  - UploadResponse / DocumentInfo / DocumentListResponse models; MAX_UPLOAD_BYTES; _is_allowed_upload
  - vercel.json rewrites /upload + /documents/:path*; functions.api/index.py.maxDuration=60
affects: [03-03, 03-04]

# Tech tracking
tech-stack:
  added:
    - "python-multipart>=0.0.9 (required by FastAPI UploadFile/File — plan omitted it; see Deviations)"
  patterns:
    - "Size + content-type guards run BEFORE ingest (a >2 MB body never reaches embedding)"
    - "Session-scoped list query: WHERE d.session_id = %s, LEFT JOIN document_chunks, GROUP BY, ORDER BY created_at DESC"
    - "GET /documents route registered before the serve_frontend /{path:path} catch-all so it is not shadowed"

key-files:
  created:
    - backend/tests/test_rag_api.py
  modified:
    - backend/api.py
    - vercel.json

key-decisions:
  - "content = await file.read() then len-check (Vercel already caps body at 4.5 MB; 2 MB app cap returns a clean 413)"
  - "Allowed = application/pdf OR text/* OR filename .pdf/.txt/.md; everything else 415"
  - "pool None on /documents returns an empty list (graceful) rather than 503, matching memory degraded-mode"

requirements-completed: [RAG-01, RAG-03, RAG-04, RAG-07]

coverage:
  - id: U1
    description: "POST /upload ingests a multipart file and returns chunks_stored"
    requirement: RAG-01
    verification:
      - kind: unit
        ref: "tests/test_rag_api.py::UploadEndpointTests::test_upload_returns_chunk_count"
        status: pass
      - kind: e2e
        ref: "live curl/browser upload — pending (human-verify after 03-03)"
        status: pending
  - id: U2
    description: ">2 MB body rejected with 413 before ingest; unsupported type rejected 415; pool None -> 503"
    requirement: RAG-04
    verification:
      - kind: unit
        ref: "tests/test_rag_api.py::UploadEndpointTests::test_size_cap_returns_413, ::test_unsupported_type_returns_415, ::test_pool_none_returns_503"
        status: pass
  - id: U3
    description: "GET /documents/{session_id} returns per-session filename + integer chunk_count; non-UUID -> 400"
    requirement: RAG-07
    verification:
      - kind: unit
        ref: "tests/test_rag_api.py::DocumentListEndpointTests::test_list_structure, ::test_invalid_session_400"
        status: pass

# Metrics
duration: inline
completed: 2026-07-02
status: complete
---

# Phase 3 Plan 02: Upload + Documents Endpoints Summary

**The HTTP surface for ingestion: a guarded `/upload` endpoint (413/415/503) and a session-scoped `/documents/{session_id}` list, both dual-routed and reachable under Vercel with maxDuration:60.**

## Accomplishments
- `backend/api.py`: `UploadResponse`/`DocumentInfo`/`DocumentListResponse` models; `MAX_UPLOAD_BYTES` (2 MB); `_is_allowed_upload`; `upload_document` (dual route, size→type→ingest order) and `list_documents` (UUID-validated, `WHERE d.session_id = %s` LEFT JOIN/GROUP BY). Both list routes are placed before the frontend catch-all so they resolve.
- `vercel.json`: `/upload` and `/documents/:path*` rewrites + top-level `functions.api/index.py.maxDuration = 60`.
- `backend/tests/test_rag_api.py` — 6 tests.

## Verification
- 6 new tests green; full backend suite: 98 green. `python -c "import json; json.load(open('vercel.json'))"` OK. Route registration confirmed: `/upload`, `/api/upload`, `/documents/{session_id}`, `/api/documents/{session_id}`.
- Live upload round-trip NOT exercised (no server/DB in session) — human-verify after 03-03.

## Task Commits
USER commits manually — NO commits made here; all edits uncommitted.

## Deviations from Plan
**1. Added `python-multipart>=0.0.9`.** FastAPI's `UploadFile`/`File` raises at import without it ("Form data requires python-multipart"). The plan listed no such dependency; it is mandatory for multipart uploads. It is a standard, ubiquitous FastAPI dependency (installed `0.0.32`), so it was added to all three requirements files without a separate supply-chain gate. **Flagged for user review.**

## User Setup Required
None new. Requires a Vercel redeploy after commit for the new routes + maxDuration to take effect (api/requirements.txt now carries pypdf + python-multipart — see [[vercel-requirements-drift]]).

---
*Phase: 03-rag* · *Completed: 2026-07-02*
