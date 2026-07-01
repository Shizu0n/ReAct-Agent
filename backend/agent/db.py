from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def _pooler_url() -> str:
    url = os.environ.get("SUPABASE_POOLER_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_POOLER_URL is not set")
    return url


def _direct_url() -> str:
    url = os.environ.get("SUPABASE_DIRECT_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_DIRECT_URL is not set")
    return url


@asynccontextmanager
async def pooler_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Async connection to Supabase Transaction Pooler (port 6543).

    Use for all application queries. prepare_threshold=None disables prepared
    statements, which are incompatible with Supavisor (PgBouncer) transaction
    mode; autocommit and dict_row are required by the Phase-2 AsyncPostgresSaver.
    """
    async with await psycopg.AsyncConnection.connect(
        _pooler_url(),
        prepare_threshold=None,   # required: Supavisor transaction mode
        autocommit=True,          # required: AsyncPostgresSaver (Phase 2)
        row_factory=dict_row,     # required: AsyncPostgresSaver (Phase 2)
    ) as conn:
        yield conn


async def create_pool(min_size: int = 1, max_size: int = 3) -> AsyncConnectionPool:
    """Create an unopened AsyncConnectionPool for the Supabase Transaction Pooler.

    The pool must be opened by the caller (`await pool.open()`). Settings mirror
    pooler_connection: prepare_threshold=None disables prepared statements (required
    for Supavisor transaction mode), autocommit=True and dict_row are required by
    AsyncPostgresSaver / AsyncPostgresStore.
    """
    pool = AsyncConnectionPool(
        conninfo=_pooler_url(),
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "prepare_threshold": None,
            "autocommit": True,
            "row_factory": dict_row,
        },
        open=False,
    )
    return pool


@asynccontextmanager
async def direct_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Async connection to Supabase direct (port 5432).

    Use ONLY for schema migrations. Not safe under serverless concurrent load.
    """
    async with await psycopg.AsyncConnection.connect(
        _direct_url(),
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        yield conn
