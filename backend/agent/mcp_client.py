"""Dynamic MCP client: discover the companion server's tools at startup.

`discover_mcp_tools()` is called once per warm serverless instance in the FastAPI
lifespan, gated by MCP_FETCH_SERVER_URL:

- unset/empty  -> ([], []) with ZERO network calls, latency, or errors (MCP-04)
- set + reachable -> the discovered BaseTools plus their OpenAI-style schemas (MCP-02)
- set + unreachable/malformed -> ([], []) via graceful degradation; never raises
  (mirrors the `pool is None` and missing-TAVILY_API_KEY degrade paths).
"""

from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger("react_agent.mcp")

MCP_DISCOVERY_TIMEOUT = 10  # seconds; a hung cold start must not block startup


async def discover_mcp_tools() -> tuple[list[BaseTool], list[dict]]:
    """Discover MCP tools from MCP_FETCH_SERVER_URL, degrading to ([], []) on failure."""
    url = os.getenv("MCP_FETCH_SERVER_URL", "").strip()
    if not url:
        return [], []  # MCP-04: no client constructed, no network call, no latency

    # The mounted endpoint lives at /mcp/ (trailing slash); bare /mcp is shadowed by
    # the SPA catch-all. Normalize so a URL configured as ".../mcp" still reaches it.
    if not url.endswith("/"):
        url = url + "/"

    try:
        client = MultiServerMCPClient(
            {"fetch": {"transport": "http", "url": url, "timeout": MCP_DISCOVERY_TIMEOUT}}
        )
        tools = await client.get_tools()
    except Exception:
        # Terse, non-interpolated message: do not echo the url/exception into a log
        # line (the global redact_secrets scrubs configured secrets, but not this).
        logger.warning("MCP discovery failed; continuing without MCP tools")
        return [], []

    schemas = [convert_to_openai_tool(tool) for tool in tools]
    return tools, schemas
