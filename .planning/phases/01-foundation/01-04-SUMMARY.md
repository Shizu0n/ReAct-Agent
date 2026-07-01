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
requirements-completed: [FOUND-04]
requirements-partial: []
completed: 2026-06-29
status: complete
---

# Phase 1 Plan 04: Keep-Alive Endpoint + Vercel Cron

**Implemented and unit-tested the authenticated keep-alive route, registered the daily Vercel cron, and VERIFIED the live deployed round-trip (Task 3) — see "Deployed round-trip" below.**

## Accomplishments
- `backend/api.py`: `keepalive_handler` dual-registered (`@app.get("/keepalive")` + `/api/keepalive`). Reads `CRON_SECRET` via `os.getenv`; returns 401 (no DB touch) on missing/wrong bearer; on success lazily imports `pooler_connection`, `UPDATE keepalive SET pinged_at=%s WHERE id=1` inside try/except (500 on DB failure, logged via redacting logger), returns `{status:"ok", pinged_at:iso}`. Added `import os` and `Response`.
- `vercel.json`: top-level `crons` (`/api/keepalive`, `0 0 * * *` — Hobby max, fires 7× in the 7-day window) + `/keepalive` rewrite to `/api/index.py`.
- `backend/tests/test_api.py`: 3 tests with a mocked async `pooler_connection` — valid Bearer → 200 + UPDATE issued; wrong token → 401 + no write; missing token → 401 + no write.

## Verification (so far)
- `python -m unittest tests.test_api` → 15 tests OK (incl. 3 keepalive).
- `vercel.json` cron + rewrite assertion → OK.
- Full suite `unittest discover` → 58 tests OK, no regressions.

## Deployed round-trip — VERIFIED 2026-06-29
- Deployed URL: `https://react-agent-ml.vercel.app`
- `GET /api/keepalive` without token → **401** (auth gate works).
- `GET /api/keepalive` with `Bearer $CRON_SECRET` → **200** `{status:"ok", pinged_at:"2026-06-30T00:08:48Z"}`.
- `SELECT pinged_at FROM keepalive WHERE id=1` → `2026-06-30 00:08:48+00` (age ~19s) — the live write landed.
- Daily cron `0 0 * * *` registered and firing on schedule (Vercel runtime logs show a 00:00 UTC invocation).

**Deploy fix required to pass this gate:** the Vercel function builds from `api/requirements.txt`, which lacked `psycopg` (only `backend/requirements.txt` had it) — the endpoint 500'd with `ModuleNotFoundError: No module named 'psycopg'`. Fixed by adding `psycopg[binary]>=3.2.0` to `api/requirements.txt` + root `requirements.txt`, then redeploy. NOTE: the deploy still runs `langgraph==0.2.45` (pre-upgrade) and lacks `psycopg-pool` / `langgraph-checkpoint-postgres` — Phase 2 must add these to api/requirements.txt before AsyncPostgresSaver will work in production.
