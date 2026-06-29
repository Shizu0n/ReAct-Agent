---
phase: 01-foundation
plan: 04
subsystem: infra
requires: [01-03]
provides:
  - Authenticated keepalive endpoint (/keepalive + /api/keepalive) with CRON_SECRET bearer check
  - Vercel daily cron (0 0 * * *) + bare-path rewrite
  - Unit tests for the auth gate (200 valid / 401 invalid / no-write)
affects: [demo-uptime]
key-files:
  modified:
    - backend/api.py
    - backend/tests/test_api.py
    - vercel.json
requirements-completed: []
requirements-partial: [FOUND-04]
completed: 2026-06-29
status: code-complete-deploy-verify-pending
---

# Phase 1 Plan 04: Keep-Alive Endpoint + Vercel Cron

**Implemented and unit-tested the authenticated keep-alive route and registered the daily Vercel cron. The live deployed round-trip (Task 3) is the one remaining gate — it requires the commit+push that triggers the Vercel deploy and the Vercel env re-pointed to the new Supabase project.**

## Accomplishments
- `backend/api.py`: `keepalive_handler` dual-registered (`@app.get("/keepalive")` + `/api/keepalive`). Reads `CRON_SECRET` via `os.getenv`; returns 401 (no DB touch) on missing/wrong bearer; on success lazily imports `pooler_connection`, `UPDATE keepalive SET pinged_at=%s WHERE id=1` inside try/except (500 on DB failure, logged via redacting logger), returns `{status:"ok", pinged_at:iso}`. Added `import os` and `Response`.
- `vercel.json`: top-level `crons` (`/api/keepalive`, `0 0 * * *` — Hobby max, fires 7× in the 7-day window) + `/keepalive` rewrite to `/api/index.py`.
- `backend/tests/test_api.py`: 3 tests with a mocked async `pooler_connection` — valid Bearer → 200 + UPDATE issued; wrong token → 401 + no write; missing token → 401 + no write.

## Verification (so far)
- `python -m unittest tests.test_api` → 15 tests OK (incl. 3 keepalive).
- `vercel.json` cron + rewrite assertion → OK.
- Full suite `unittest discover` → 58 tests OK, no regressions.

## Remaining (Task 3 — blocking human-verify, post-deploy)
1. Re-point Vercel env to the new Supabase project (`SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET`) — the project was re-created during Plan 02.
2. Push to deploy → Vercel builds.
3. `curl -H "Authorization: Bearer $CRON_SECRET" .../api/keepalive` → 200; without header → 401; `SELECT pinged_at FROM keepalive WHERE id=1` fresh; daily cron registered in Vercel dashboard. Resume signal: "keepalive live".
