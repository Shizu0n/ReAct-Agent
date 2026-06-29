---
phase: 1
slug: foundation
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — uses `python -m unittest discover` |
| **Quick run command** | `cd backend && python -m unittest discover -s tests -v` |
| **Full suite command** | `cd backend && python -m unittest discover -s tests -v` (all 5 modules) |
| **Estimated runtime** | ~3–8 seconds (no live DB; DB smokes run separately) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m unittest discover -s tests -v`
- **After every plan wave:** Full suite + the wave's DB smoke (`verify_db.py` / `verify_schema.py`)
- **Before `/gsd-verify-work`:** Full suite green AND all 4 Roadmap success criteria observably TRUE
- **Max feedback latency:** ~10 seconds for unit suite; DB smokes gated by live Supabase env

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | FOUND-05 | T-01-UP | Upgrade preserves behavior | regression | `grep -aoE "langgraph>=[0-9.]+" requirements.txt` | ✅ existing | ⬜ pending |
| 01-01-02 | 01 | 1 | FOUND-05 | T-01-SC | Supply chain verified pre-install | regression | `python -m unittest discover -s tests -v` | ✅ existing | ⬜ pending |
| 01-02-01 | 02 | 2 | FOUND-02 | T-01-01 | Supabase conn-string value redacted | unit | `python -m unittest tests.test_redaction -v` | ✅ existing (edit) | ⬜ pending |
| 01-02-03 | 02 | 2 | FOUND-02, FOUND-01 | T-01-04 | Pooler-only (6543), no prep stmts | smoke | `python scripts/verify_db.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | FOUND-03 | T-01-05 | Idempotent additive DDL | schema | `grep -c "USING hnsw" .planning/phases/01-foundation/migration.sql` | ❌ W0 | ⬜ pending |
| 01-03-03 | 03 | 3 | FOUND-03, FOUND-01 | — | Schema live (4 tables + HNSW) | schema check | `python scripts/verify_schema.py` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 4 | FOUND-04 | T-01-02 | CRON_SECRET bearer gate (401 on mismatch) | unit | `python -m unittest tests.test_api -v` | ✅ existing (edit) | ⬜ pending |
| 01-04-02 | 04 | 4 | FOUND-04 | T-01-02 | Daily cron only (Hobby limit) | config | `python -c "import json; json.load(open('vercel.json'))"` | ✅ (edit) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/agent/db.py` — connection factory (new; Plan 02 Task 1)
- [ ] `backend/scripts/verify_db.py` — pooler smoke `SELECT NOW()` (new; Plan 02 Task 3)
- [ ] `backend/scripts/verify_schema.py` — asserts 4 tables + HNSW index live (new; Plan 03 Task 3)
- [ ] `.planning/phases/01-foundation/migration.sql` authored AND applied to live Supabase (Plan 03)
- [ ] `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` set locally + in Vercel (Plan 02 checkpoint)
- [ ] `backend/tests/test_redaction.py` — Supabase-URL redaction case (edit; Plan 02 Task 1)
- [ ] `backend/tests/test_api.py` — keepalive 200/401 auth tests (edit; Plan 04 Task 1)

*FOUND-05 (existing 5-module unit suite) needs no new scaffolding — it IS the regression gate.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live pooler connection returns a timestamp | FOUND-02 | Needs a provisioned Supabase project + real connection string | After env vars set: `cd backend && python scripts/verify_db.py` (exits 0 with a timestamp) |
| 4 tables + HNSW index exist in Supabase | FOUND-03 | Schema must be APPLIED to the live DB, then visually confirmed | `python scripts/verify_schema.py` exits 0; Supabase Table Editor lists the 4 tables + single keepalive row |
| Deployed cron round-trip + registered schedule | FOUND-04 | Cron fires on a Vercel schedule; deploy + dashboard required | `curl -H "Authorization: Bearer $CRON_SECRET" https://<app>/api/keepalive` → 200; no header → 401; `SELECT pinged_at FROM keepalive WHERE id=1` fresh; cron listed in Vercel Settings → Cron Jobs |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s (unit suite); DB smokes gated by live env
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-29
