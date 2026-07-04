from __future__ import annotations

import logging

from psycopg.types.json import Json

from agent.redaction import redact_secrets

logger = logging.getLogger("react_agent.traces")

_REDACTED_STEP_FIELDS = ("thought", "observation", "action_input")


def _redact_steps(steps: list[dict]) -> list[dict]:
    """Return a shallow-copied step list with secret values scrubbed from the
    string fields, leaving the live response untouched."""
    redacted: list[dict] = []
    for step in steps:
        item = dict(step)
        for field in _REDACTED_STEP_FIELDS:
            if isinstance(item.get(field), str):
                item[field] = redact_secrets(item[field])
        redacted.append(item)
    return redacted


async def persist_trace(pool, run_id, thread_id, user_id, query, response) -> None:
    """Insert a completed run into the traces table. No-op when pool is None.
    thread_id scopes the conversation; user_id scopes the browser identity.
    Steps and final_answer are redaction-scrubbed; steps and usage are JSONB."""
    if pool is None:
        return
    steps = _redact_steps(response.steps)
    final_answer = redact_secrets(response.answer)
    params = (
        run_id,
        thread_id,
        user_id,
        query,
        Json(steps),
        final_answer,
        response.status,
        Json(response.usage),
        response.latency_ms,
    )
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO traces
                (run_id, thread_id, user_id, query, steps, final_answer, status, usage, elapsed_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            params,
        )


async def fetch_runs(pool, user_id, limit: int = 50) -> list[dict]:
    """User-scoped run summaries (every conversation), newest first.
    Empty list when pool is None."""
    if pool is None:
        return []
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT run_id, thread_id, query, status, elapsed_ms, usage, created_at
            FROM traces
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return await cur.fetchall()


async def fetch_trace(pool, run_id, user_id) -> dict | None:
    """Single persisted trace row scoped to its owning user, or None when
    absent / not owned by user_id / pool is None."""
    if pool is None:
        return None
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM traces WHERE run_id = %s AND user_id = %s",
            (run_id, user_id),
        )
        return await cur.fetchone()


def _response_from_row(row):
    """Rebuild an AgentResponse from a persisted traces row."""
    import api

    steps = row.get("steps") or []
    elapsed_ms = row.get("elapsed_ms") or 0
    final_answer = row.get("final_answer") or ""
    tools_used = list(
        dict.fromkeys(step["action"] for step in steps if step.get("action"))
    )
    return api.AgentResponse(
        result=final_answer,
        trace=steps,
        total_time=elapsed_ms / 1000,
        run_id=row["run_id"],
        answer=final_answer,
        steps=steps,
        tools_used=tools_used,
        latency_ms=elapsed_ms,
        status=row.get("status") or "success",
        usage=row.get("usage") or {},
    )
