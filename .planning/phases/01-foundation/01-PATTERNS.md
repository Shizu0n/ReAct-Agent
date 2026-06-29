# Phase 1: Foundation - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 6 (2 new, 4 edits)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/agent/db.py` | utility | request-response (async context manager) | `backend/agent/redaction.py` | role-match (module-level utility, no class) |
| `backend/api.py` (edit: /keepalive route) | route | request-response | `backend/api.py` lines 378-381 (`/health` route) | exact |
| `backend/requirements.txt` (edit) | config | — | `backend/requirements.txt` (self) | exact |
| `.env.example` (edit) | config | — | `.env.example` (self — content pattern from RESEARCH.md) | exact |
| `vercel.json` (edit: add crons) | config | — | `vercel.json` (self) | exact |
| `.planning/phases/01-foundation/migration.sql` | migration | batch | none (no SQL files exist in codebase) | no-analog |

---

## Pattern Assignments

### `backend/agent/db.py` (utility, request-response)

**Analog:** `backend/agent/redaction.py` — module-level utility with no class, private helper functions, `from __future__ import annotations`, `os.environ` access with RuntimeError on missing values.

**Imports pattern** (`backend/agent/redaction.py` lines 1-7):
```python
from __future__ import annotations

import logging
import os
import re
from typing import Any
```

**Env-var-with-RuntimeError pattern** (mirror of `configured_secret_values()` style in `redaction.py` lines 17-23):
```python
def _pooler_url() -> str:
    url = os.environ.get("SUPABASE_POOLER_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_POOLER_URL is not set")
    return url
```
Rationale: The project pattern for missing env vars is RuntimeError (not sys.exit, not a default). `configure_secure_logging()` is called at module import in `api.py` (line 29); `db.py` should follow the same import-time-safe pattern — raise only at call time, not at import time.

**Secret redaction invariant for db.py:** The values of `SUPABASE_POOLER_URL` and `SUPABASE_DIRECT_URL` contain passwords. They will be covered automatically by `configured_secret_values()` in `redaction.py` (line 22: matches any env var name containing `PASSWORD`). However, the URL contains the password *inline* in the string. Verify that `redaction.py` `SECRET_ENV_MARKERS` covers `"PASSWORD"` (it does, line 10) and that the full URL value (which contains the password) gets scraped by the value-substitution pass (lines 29-31 of redaction.py). No additional action needed — the existing redaction covers it.

**Context manager pattern** (from RESEARCH.md Pattern 1 — no existing async context manager analog in codebase):
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import psycopg
from psycopg.rows import dict_row

@asynccontextmanager
async def pooler_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    async with await psycopg.AsyncConnection.connect(
        _pooler_url(),
        prepare_threshold=None,   # required: Supavisor transaction mode
        autocommit=True,          # required: AsyncPostgresSaver (Phase 2)
        row_factory=dict_row,     # required: AsyncPostgresSaver (Phase 2)
    ) as conn:
        yield conn
```

**No module-level singleton:** `backend/api.py` uses `build_graph()` (called per-request, line 201 and 261) rather than a module-level graph object. Follow the same per-request pattern for DB connections — no module-level `conn` variable.

---

### `backend/api.py` — add `/keepalive` + `/api/keepalive` routes (route, request-response)

**Analog:** `backend/api.py` lines 378-381 (`/health` route — simplest existing GET with dual registration).

**Dual-registration pattern** (lines 378-381):
```python
@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tools": list(TOOLS.keys())}
```
The keepalive route follows the identical decorator stacking: bare path first, `/api/` prefixed second.

**Auth guard pattern** (no existing analog — this is the first authenticated route):
```python
from fastapi.responses import Response  # already imported at top of api.py

@app.get("/keepalive")
@app.get("/api/keepalive")
async def keepalive_handler(request: Request) -> dict:
    cron_secret = os.getenv("CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    if cron_secret and auth != f"Bearer {cron_secret}":
        return Response(status_code=401)
    ...
```
Note: `Request` is already imported in `api.py` (line 14). `Response` needs to be added to the FastAPI import line. `os` is NOT currently imported in `api.py` — use `os.getenv` requires adding `import os` at the top.

**Import check for `api.py`:** Current imports (lines 1-27) do NOT include `import os`. Add `import os` to the stdlib block. `datetime` and `timezone` are already imported (line 9).

**Lazy import pattern for agent.db** (mirrors the pattern in `api.py` where `agent.*` imports are at module top, lines 23-27). For the keepalive handler, import `pooler_connection` inside the function body to avoid import-time failure when `SUPABASE_POOLER_URL` is not set (so existing routes still work in dev without Supabase configured):
```python
async def keepalive_handler(request: Request) -> dict:
    ...
    from agent.db import pooler_connection  # lazy: don't break dev without SUPABASE vars
    async with pooler_connection() as conn:
        await conn.execute(
            "UPDATE keepalive SET pinged_at = %s WHERE id = 1",
            (datetime.now(timezone.utc),),
        )
    return {"status": "ok", "pinged_at": datetime.now(timezone.utc).isoformat()}
```

**Logger pattern** (`api.py` line 30): `logger = logging.getLogger("react_agent.api")` — the keepalive handler can use this same logger for any error logging (it's module-scope, no change needed).

**Error handling pattern** (`api.py` lines 315-326 in `_stream_agent`):
```python
except Exception as exc:
    logger.exception("Agent stream failed for run %s", run_id)
    ...
```
For the keepalive route, wrap the DB call in try/except and return HTTP 500 on failure rather than propagating:
```python
    try:
        async with pooler_connection() as conn:
            await conn.execute(...)
    except Exception:
        logger.exception("keepalive DB write failed")
        return Response(status_code=500)
```

**vercel.json rewrite required:** Add `{ "source": "/keepalive", "destination": "/api/index.py" }` to the rewrites array (following the pattern of `/health` at line 29 of vercel.json).

---

### `backend/requirements.txt` (config edit)

**Analog:** Self — current `requirements.txt` (read above, space-separated encoding artifact is display-only; actual file uses standard pip format).

**Current LangChain ecosystem pins (lines 27-34 of requirements.txt):**
```
langchain==0.3.7
langchain-community==0.3.7
langchain-core==0.3.63
langchain-text-splitters==0.3.8
langgraph==0.2.45
langgraph-checkpoint==2.1.2
langgraph-sdk==0.1.74
langsmith==0.1.147
```

**Target changes — replace exact pins with minimums, add new packages:**
```
# CHANGE: == → >= for the full LangChain ecosystem
langchain>=1.3.11
langchain-community>=0.4.2
langchain-core>=1.4.8
langchain-text-splitters>=1.1.2
langgraph>=1.2.6
langsmith>=0.9.3

# REMOVE explicit pins (resolved transitively):
# langgraph-checkpoint  ← omit; pulled by langgraph-checkpoint-postgres
# langgraph-sdk         ← omit; pulled by langgraph

# ADD new Phase 1 packages:
langgraph-checkpoint-postgres>=3.1.0
psycopg[binary]>=3.2.0
psycopg-pool>=3.2.0
```

**DO NOT change:** `numpy==1.26.4` (Python 3.13 wheel constraint documented in CLAUDE.md). All non-LangChain packages keep their current pins.

---

### `.env.example` (config edit)

**Analog:** Self — existing `.env.example` format (not directly readable per CLAUDE.md secret-file deny, but format known from RESEARCH.md code example and existing pattern of `KEY=value` with comments).

**Pattern to append:**
```bash
# Supabase — get from Supabase dashboard → Project Settings → Database
# Transaction Pooler (port 6543) — use for ALL application queries
SUPABASE_POOLER_URL=postgresql://postgres.PROJECTREF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres

# Direct connection (port 5432) — use ONLY for schema migrations
SUPABASE_DIRECT_URL=postgresql://postgres:PASSWORD@db.PROJECTREF.supabase.co:5432/postgres

# Vercel Cron Security — set in Vercel dashboard; Vercel sends as Authorization: Bearer <value>
CRON_SECRET=<random-32-char-string>
```

---

### `vercel.json` (config edit)

**Analog:** Self — current `vercel.json` (read above, lines 1-37).

**Existing structure to preserve:** `buildCommand`, `outputDirectory`, `headers`, `rewrites` array.

**Add at top level (new `crons` key):**
```json
{
  "crons": [
    {
      "path": "/api/keepalive",
      "schedule": "0 0 * * *"
    }
  ]
}
```

**Add to `rewrites` array** (after the `/trace/:path*` entry, before the SPA catch-all):
```json
{ "source": "/keepalive", "destination": "/api/index.py" }
```
This follows the bare-path rewrite pattern used for `/health` (line 29), `/config` (line 30), `/suggestions` (line 31).

---

### `.planning/phases/01-foundation/migration.sql` (migration, batch)

**No analog in codebase** — no SQL files exist. Full SQL provided verbatim in RESEARCH.md (Schema Migration SQL section, lines 292-355 of RESEARCH.md). Use that content directly; no codebase pattern to mirror.

**Key constraints from RESEARCH.md:**
- All statements use `IF NOT EXISTS` (idempotent).
- `keepalive` seeded with `ON CONFLICT (id) DO NOTHING`.
- `AsyncPostgresSaver` checkpoint tables are NOT pre-created here — let Phase 2 call `checkpointer.setup()`.
- Run via Supabase dashboard SQL editor or `supabase db push` against direct URL (port 5432), not the pooler.

---

## Shared Patterns

### Dual Route Registration
**Source:** `backend/api.py` lines 354-357, 368-370, 378-381
**Apply to:** The new `/keepalive` route
```python
@app.get("/keepalive")
@app.get("/api/keepalive")
async def handler(...):
    ...
```
Every new route must appear in both bare and `/api/`-prefixed form AND have a bare-path rewrite entry in `vercel.json`.

### Env Var Access + RuntimeError on Missing
**Source:** `backend/agent/redaction.py` lines 17-24 (pattern); `backend/agent/llms.py` (provider key checks)
**Apply to:** `backend/agent/db.py` private URL helper functions
```python
def _pooler_url() -> str:
    url = os.environ.get("SUPABASE_POOLER_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_POOLER_URL is not set")
    return url
```

### Secret Redaction Coverage
**Source:** `backend/agent/redaction.py` lines 10, 22-23
**Apply to:** No code change needed — `SUPABASE_POOLER_URL` and `SUPABASE_DIRECT_URL` contain `PASSWORD` in their value strings (the URL embeds the password). The existing `SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")` pattern matches any env var *name* containing these strings. `SUPABASE_POOLER_URL` does not contain a marker in the var name, but the full URL *value* will be scraped by the value-substitution pass (lines 29-31) because the value equals the full env var value, which gets redacted as a whole unit. Verify during smoke test by checking no URL appears in logs.

### Module Import Style
**Source:** `backend/agent/redaction.py` line 1; `backend/api.py` line 1
**Apply to:** `backend/agent/db.py`
```python
from __future__ import annotations
```
All backend modules start with this line.

### Logger Naming
**Source:** `backend/api.py` line 30
**Apply to:** If `db.py` needs a logger (for connection errors):
```python
logger = logging.getLogger("react_agent.db")
```

### Test Structure
**Source:** `backend/tests/test_api.py` lines 99-111 (setUp/tearDown + TestClient + mock injection)
**Apply to:** Any new test for the keepalive route — use `TestClient`, mock `build_graph` injection pattern, test both 200 (valid token) and 401 (wrong token) responses. RESEARCH.md marks keepalive integration test as a Wave 0 gap with no existing test — a unit test with a mocked `pooler_connection` covers the auth logic without needing a real DB.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.planning/phases/01-foundation/migration.sql` | migration | batch | No SQL migration files exist in the codebase; full SQL provided in RESEARCH.md |

---

## Metadata

**Analog search scope:** `backend/agent/`, `backend/api.py`, `backend/tests/`, `vercel.json`, `backend/requirements.txt`
**Files read:** 6 source files
**Pattern extraction date:** 2026-06-29
