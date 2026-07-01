from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / ".env")

from agent.db import direct_connection


async def main() -> int:
    """Create or upgrade LangGraph checkpoint and store tables via the direct connection.

    Uses the Supabase direct connection (port 5432) because the DDL run by
    AsyncPostgresSaver.setup() includes CONCURRENTLY index creation, which is
    incompatible with Supavisor transaction mode (port 6543).

    The script is idempotent: setup() consults its own migration-version tables
    and short-circuits migrations that have already been applied, so re-running
    is safe.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.store.postgres import AsyncPostgresStore

    async with direct_connection() as conn:
        checkpointer = AsyncPostgresSaver(conn=conn)
        checkpointer.supports_pipeline = False
        store = AsyncPostgresStore(conn=conn)
        store.supports_pipeline = False

        print("Running AsyncPostgresSaver.setup() ...")
        await checkpointer.setup()
        print("Running AsyncPostgresStore.setup() ...")
        await store.setup()

        # Verify the three core tables are present.
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT "
                "to_regclass('public.checkpoints') AS checkpoints,"
                "to_regclass('public.checkpoint_writes') AS checkpoint_writes,"
                "to_regclass('public.store') AS store"
            )
            row = await cur.fetchone()

    if row is None:
        print("ERROR: verification query returned no rows", file=sys.stderr)
        return 1

    checkpoints = row["checkpoints"]
    checkpoint_writes = row["checkpoint_writes"]
    store_table = row["store"]

    print(
        f"checkpoints        : {checkpoints}\n"
        f"checkpoint_writes  : {checkpoint_writes}\n"
        f"store              : {store_table}"
    )

    missing = [
        name
        for name, val in [
            ("checkpoints", checkpoints),
            ("checkpoint_writes", checkpoint_writes),
            ("store", store_table),
        ]
        if val is None
    ]
    if missing:
        print(
            f"ERROR: the following tables are still NULL after setup: {missing}",
            file=sys.stderr,
        )
        return 1

    print("setup_memory_schema OK — all tables present")
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
        print(f"setup_memory_schema FAILED: {message}", file=sys.stderr)
        sys.exit(1)
