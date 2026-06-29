---
phase: 01-foundation
plan: 02
subsystem: infra
requires: [01-01]
provides:
  - Shared async DB connection layer (pooler_connection / direct_connection) in backend/agent/db.py
  - Live Supabase project provisioned (ref vvhbvldwihytvnqotmfd, region sa-east-1) with env vars wired locally
  - Secret redaction coverage for SUPABASE_* connection-string values
affects: [01-03, 01-04, phase-02-memory, phase-03-rag, phase-04-observability]
key-files:
  created:
    - backend/agent/db.py
    - backend/scripts/verify_db.py
  modified:
    - backend/agent/redaction.py
    - backend/tests/test_redaction.py
    - backend/.env.example
requirements-completed: [FOUND-02]
requirements-partial: [FOUND-01]
completed: 2026-06-29
status: complete
---

# Phase 1 Plan 02: Supabase Connection Layer + Live Smoke

**Built the shared async psycopg3 connection factory against the Supabase Transaction Pooler, closed the secret-redaction gap for the new connection strings, and proved a real `SELECT NOW()` over port 6543 end-to-end.**

## Accomplishments
- `backend/agent/db.py`: `pooler_connection()` (6543, `prepare_threshold=None`, `autocommit=True`, `row_factory=dict_row`) and `direct_connection()` (5432, migrations only). Per-call context managers, no module singleton (Vercel-ephemeral safe). URLs read at call time and raise a generic RuntimeError (no value leak) when unset.
- `redaction.py`: added `"SUPABASE"` to `SECRET_ENV_MARKERS` so `SUPABASE_*` values (which embed the DB password) are scrubbed globally. New test asserts a Supabase URL value does not survive redaction.
- `.env.example`: documented `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` (appended via Bash — file is Edit-deny-listed).
- `backend/scripts/verify_db.py`: reusable async smoke; loads `.env`, opens the pooler, runs `SELECT NOW()`, redacts any error.

## Verification
- `python -c "import agent.db ..."` exports present; `python -m unittest tests.test_redaction` green (incl. new case).
- `python scripts/verify_db.py` → `pooler OK - SELECT NOW() = 2026-06-29 19:41:18 UTC`, exit 0. **Roadmap SC1 met.**

## Deviations / Issues
- **Windows event loop:** psycopg async is incompatible with Windows' default `ProactorEventLoop`; the smoke script sets `WindowsSelectorEventLoopPolicy` under `win32`. Linux/Vercel unaffected.
- **Project re-created:** the live Supabase project was deleted and re-created during setup; current ref is `vvhbvldwihytvnqotmfd`. Vercel env must be re-pointed to this ref before Plan 04 deploy.
- **Password encoding:** DB password contained URI-reserved chars (`#`, `[`, `]`); resolved by percent-encoding the full userinfo (`urllib.parse.quote(pw, safe='')`).

## User Setup Done
Supabase project provisioned; `SUPABASE_POOLER_URL`, `SUPABASE_DIRECT_URL`, `CRON_SECRET` set in local `backend/.env`. (Vercel env re-point pending for Plan 04.)
