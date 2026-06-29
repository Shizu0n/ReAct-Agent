from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / ".env")

from agent.db import pooler_connection


async def main() -> None:
    """Open the Transaction Pooler and run a real query (FOUND-02 / SC1)."""
    async with pooler_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT NOW()")
            row = await cur.fetchone()
    print(f"pooler OK - SELECT NOW() = {row}")


if __name__ == "__main__":
    # psycopg async is incompatible with Windows' default ProactorEventLoop.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except Exception as exc:
        from agent.redaction import redact_secrets

        message = redact_secrets(f"{type(exc).__name__}: {exc}")
        print(f"pooler smoke FAILED: {message}", file=sys.stderr)
        sys.exit(1)
