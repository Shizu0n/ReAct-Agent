---
phase: 03-rag
plan: 04
subsystem: agent
tags: [langgraph, tool, pgvector, retrieval, citations, prompt-injection]

# Dependency graph
requires:
  - phase: 03-01
    provides: agent.embedding.embed_query
  - phase: 03-02
    provides: documents/document_chunks populated via /upload
  - phase: 02-memory
    provides: memory_read/write tool-node pattern, build_graph store/config injection, prompts.py barrier style
provides:
  - document_search tool (TOOL_SCHEMAS + TOOL_INPUT_KEYS + tool_node dispatch), session-scoped cosine pgvector retrieval
  - _run_document_search — cited passages behind BEGIN/END RETRIEVED DOCUMENTS barrier + no-hallucination no-result message
  - build_graph(pool=...) closure injecting pool into tool_node; api.py threads pool from app.state
  - SYSTEM_PROMPT directives: document_search usage, citation, no-general-knowledge, retrieved-content injection barrier
affects: [04-observability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pool injected into tool_node via a build_graph closure (same shape as store/config injection), not config.configurable"
    - "Cosine distance operator <=> against the HNSW vector_cosine_ops index (never <-> L2)"
    - "Retrieved content wrapped in --- BEGIN/END RETRIEVED DOCUMENTS --- and treated as untrusted by SYSTEM_PROMPT"
    - "1-based citation display: [Source: filename, chunk chunk_index+1]"

key-files:
  created:
    - backend/tests/test_document_search.py
    - backend/tests/test_rag_security.py
  modified:
    - backend/agent/graph.py
    - backend/agent/prompts.py
    - backend/api.py

key-decisions:
  - "Retrieval SELECT drops the similarity column (only ORDER BY <=> is needed); binds (session_id, vec_str)"
  - "No-result and no-documents collapse into one explicit no-content message (prompt forbids answering from general knowledge)"
  - "pool guard both in tool_node dispatch and inside _run_document_search (defensive)"

requirements-completed: [RAG-05, RAG-06, RAG-08, RAG-09]

coverage:
  - id: S1
    description: "document_search is dispatched in tool_node and emits a 5-key Step (thought/action/action_input/observation/timestamp)"
    requirement: RAG-05
    verification:
      - kind: unit
        ref: "tests/test_document_search.py::DocumentSearchStepTests::test_step_shape"
        status: pass
  - id: S2
    description: "Successful retrieval formats [Source: filename, chunk N] (1-based) inside BEGIN/END markers"
    requirement: RAG-06
    verification:
      - kind: unit
        ref: "tests/test_document_search.py::CitationTests::test_citation_format; tests/test_rag_security.py::InjectionBarrierTests::test_barrier_markers"
        status: pass
  - id: S3
    description: "Empty/irrelevant retrieval returns an explicit no-content message; pool None -> unavailable"
    requirement: RAG-08
    verification:
      - kind: unit
        ref: "tests/test_document_search.py::NoResultTests::test_no_docs, ::test_pool_none"
        status: pass
  - id: S4
    description: "Retrieval is session-scoped (dc.session_id = %s) and uses the cosine operator"
    requirement: RAG-05
    verification:
      - kind: unit
        ref: "tests/test_document_search.py::SessionScopeTests::test_query_filters_session"
        status: pass
  - id: S5
    description: "SYSTEM_PROMPT carries the retrieved-content barrier + citation + no-general-knowledge directives"
    requirement: RAG-09
    verification:
      - kind: unit
        ref: "tests/test_rag_security.py::PromptDirectiveTests::test_prompt_has_barrier_and_citation"
        status: pass
  - id: S6
    description: "Cited, trace-visible answer for a covered question; explicit absence for an uncovered one"
    requirement: RAG-06
    verification:
      - kind: e2e
        ref: "live: upload a doc, ask covered/uncovered questions, observe [Source:] citations + document_search Step in the panel — pending human verify"
        status: pending

# Metrics
duration: inline
completed: 2026-07-02
status: complete
---

# Phase 3 Plan 04: document_search Tool Summary

**The retrieval read-path: a session-scoped pgvector `document_search` tool that embeds the query, returns cited passages behind a prompt-injection barrier, and refuses to answer from general knowledge when nothing is retrieved — plus the pool wiring that reaches it.**

## Accomplishments
- `backend/agent/graph.py`: `DOCUMENT_SEARCH_TOOL_NAME`, `TOOL_INPUT_KEYS` entry, directive `TOOL_SCHEMAS` entry, `_run_document_search(pool, session_id, query)` (embed_query → cosine `<=>` SELECT `WHERE dc.session_id = %s` LIMIT 5 → BEGIN/END-wrapped `[Source: file, chunk N]` passages + citation/no-hallucination trailer; no-rows and pool-None messages), a `document_search` dispatch branch in `tool_node` (now `pool=None`), and a `build_graph(pool=None)` closure `_tool_node` that forwards pool while preserving store/config injection.
- `backend/agent/prompts.py`: appended a document_search usage directive (cite sources; do not answer from general knowledge when empty) and a "--- BEGIN/END RETRIEVED DOCUMENTS ---" untrusted-content barrier.
- `backend/api.py`: `_run_agent`/`_stream_agent` gained a `pool=None` param passed into `build_graph`; both route handlers read `pool = getattr(request.app.state, "pool", None)` and thread it through.
- Tests: `test_document_search.py` (5) + `test_rag_security.py` (2).

## Verification
- 7 new tests green; full backend suite: 105 green. Web-search gate tests still pass (no change to `_requires_web_search`). document_search appears in `TOOL_SCHEMAS`/`TOOL_INPUT_KEYS`/dispatch; SQL asserts `dc.session_id = %s` + `<=>`.
- Live end-to-end retrieval (real embed + pgvector + trace panel citation) NOT exercised — human-verify after deploy.

## Task Commits
USER commits manually — NO commits made here; all edits uncommitted.

## Deviations from Plan
None. Retrieval SQL simplified to drop the unused similarity column (params (session_id, vec_str)); behavior unchanged.

## User Setup Required
None new — reuses GEMINI_API_KEY + SUPABASE_POOLER_URL.

---
*Phase: 03-rag* · *Completed: 2026-07-02*
