from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / ".env")

from agent.db import pooler_connection

EXPECTED_TABLES = {"documents", "document_chunks", "traces", "keepalive"}


async def main() -> int:
    """Assert the 4 foundation tables + HNSW index exist in live Supabase (SC2)."""
    async with pooler_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' "
                "AND tablename IN ('documents','document_chunks','traces','keepalive')"
            )
            tables = {r["tablename"] for r in await cur.fetchall()}
            await cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname='chunks_embedding_hnsw_idx'"
            )
            idx = await cur.fetchall()

    missing = EXPECTED_TABLES - tables
    if missing or len(idx) != 1:
        print(
            f"schema INCOMPLETE - tables: {sorted(tables)}, "
            f"missing: {sorted(missing)}, hnsw rows: {len(idx)}",
            file=sys.stderr,
        )
        return 1
    print("4 tables, hnsw index present")
    return 0


if __name__ == "__main__":
    # psycopg async is incompatible with Windows' default ProactorEventLoop.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:
        from agent.redaction import redact_secrets

        message = redact_secrets(f"{type(exc).__name__}: {exc}")
        print(f"verify_schema FAILED: {message}", file=sys.stderr)
        sys.exit(1)
