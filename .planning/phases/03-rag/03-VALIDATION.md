---
phase: 3
slug: rag
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (backend); no frontend test framework configured |
| **Config file** | none — tests live in `backend/tests/` |
| **Quick run command** | `python -m unittest discover -s tests -v` (from `backend/`) |
| **Full suite command** | `python -m unittest discover -s tests -v` (from `backend/`) |
| **Estimated runtime** | ~30 seconds (83 tests currently green) |

---

## Sampling Rate

- **After every task commit:** Run `python -m unittest discover -s tests -v`
- **After every plan wave:** Run the full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Populated by the planner from PLAN.md task IDs. See `03-RESEARCH.md` §Validation Architecture for the per-requirement validation approach (RAG-01..09, SC1–SC5). Commands run from `backend/` unless noted.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | RAG-01 | T-3-SC | pypdf supply-chain human-verified before install | checkpoint | manual (blocking-human gate) | N/A | ⬜ pending |
| 3-01-02 | 01 | 1 | RAG-01,02,04,09 | T-3-02 | invisible-char strip + batching/backoff contract (RED) | unit | `python -m unittest tests.test_rag_ingestion -v` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | RAG-02,04,09 | T-3-02 / T-3-08 | strip + 768-dim ::vector cast + 429 backoff + 200-cap | unit | `python -m unittest tests.test_rag_ingestion -v` | ✅ (after 3-01-02) | ⬜ pending |
| 3-02-01 | 02 | 2 | RAG-01,07 | T-3-04 / T-3-05 / T-3-03a | 2MB+type guard before ingest; session-scoped list | unit | `python -m unittest tests.test_rag_api -v` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 2 | RAG-03,04 | T-3-04 | 413/415/503 paths; vercel maxDuration:60 | unit | `python -m unittest tests.test_rag_api -v` | ✅ (after 3-02-01) | ⬜ pending |
| 3-03-01 | 03 | 3 | RAG-07 | T-3-10 | session-id reused; list scoped to session | typecheck | `cd frontend && npx tsc -b --noEmit` | N/A | ⬜ pending |
| 3-03-02 | 03 | 3 | RAG-01,03,07 | T-3-09 | filename rendered as escaped text; upload UI | build | `cd frontend && npm run build` | N/A | ⬜ pending |
| 3-04-01 | 04 | 3 | RAG-05,06,08,09 | T-3-01 / T-3-03 | Step shape, citation, no-result, session scope, barrier (RED) | unit | `python -m unittest tests.test_document_search tests.test_rag_security -v` | ❌ W0 | ⬜ pending |
| 3-04-02 | 04 | 3 | RAG-05,06,08,09 | T-3-01 / T-3-03 / T-3-11 | document_search tool + barrier + citation + no-hallucination | unit | `python -m unittest tests.test_document_search tests.test_rag_security -v` | ✅ (after 3-04-01) | ⬜ pending |
| 3-04-03 | 04 | 3 | RAG-05 | T-3-03 | pool wiring reaches tool; full suite green | unit | `python -m unittest discover -s tests -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_rag_ingestion.py` — ingestion/chunking/embedding + invisible-char stripping stubs (RAG-01, RAG-02, RAG-04, RAG-09-ingest) — created in plan 03-01 Task 2
- [ ] `backend/tests/test_rag_api.py` — upload endpoint guards (413/415/503) + document-list stubs (RAG-01, RAG-03, RAG-04, RAG-07) — created in plan 03-02 Task 2
- [ ] `backend/tests/test_document_search.py` — retrieval Step shape + citation + no-hallucination + session-scope stubs (RAG-05, RAG-06, RAG-08) — created in plan 03-04 Task 1
- [ ] `backend/tests/test_rag_security.py` — prompt-injection barrier + SYSTEM_PROMPT directives (RAG-09-retrieve) — created in plan 03-04 Task 1

*Each test file is owned by exactly one plan (no cross-wave modification). RAG-09 is split: invisible-char stripping lives in `test_rag_ingestion.py` (03-01); the retrieved-content injection barrier lives in `test_rag_security.py` (03-04).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload a PDF and see progress + chunk count in the UI | RAG-01, RAG-03, RAG-07 | Requires live Supabase + Gemini embedding calls + browser | Upload a small PDF via the demo, confirm progress indicator and per-session doc list with chunk count |
| Cited answer grounded in uploaded doc | RAG-06, SC2 | Requires live retrieval over embedded chunks | Ask a question covered by the doc; confirm inline citation (filename + chunk index) |
| Absence acknowledged, no hallucination | RAG-08, SC4 | Requires live retrieval returning low-relevance chunks | Ask a question NOT covered; confirm the agent says it isn't in the documents |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (checkpoint 3-01-01 is a blocking-human gate, immediately followed by automated tasks)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 test files created before their implementations)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (RAG-only run < 5s; full suite ~30s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner, 2026-07-01)
