"""Local dev launcher. On Windows, psycopg async cannot run on the default
ProactorEventLoop, so the selector policy must be set BEFORE uvicorn creates
its loop — `python run_local.py` instead of `python -m uvicorn api:app`.
On Vercel (Linux) this file is unused."""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
