"""Tests for the companion MCP server and (Plan 05-03) the MCP client.

FetchToolTests / ServerMountTests cover Plan 05-01 (MCP-01): fetch_url extraction,
SSRF/DoS/injection hardening, and the mounted FastMCP server exposing the tool.
Discovery tests added in Plan 05-03 extend this file.
"""

import asyncio
import os
import socket
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from langchain_core.tools import StructuredTool

from agent.mcp_client import discover_mcp_tools
from agent.mcp_server import (
    BEGIN_MARKER,
    END_MARKER,
    MAX_RETURNED_CHARS,
    fetch_url,
    mcp_server,
)


def run(coro):
    return asyncio.run(coro)

# A public-looking getaddrinfo result, patched in for success-path tests so no
# real DNS lookup happens (which would fail closed offline).
_PUBLIC_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def _addrinfo(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


class _FakeResponse:
    def __init__(self, content=b"", headers=None, url="http://example.com/", encoding="utf-8"):
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.encoding = encoding

    def raise_for_status(self):
        return None


class _FakeClient:
    """Context-manager stand-in for httpx.Client whose .get is fully controlled."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        if self._exc is not None:
            raise self._exc
        return self._response


class FetchToolTests(unittest.TestCase):
    """MCP-01: fetch_url extraction + SSRF/DoS/injection hardening."""

    def test_html_extraction_wrapped_and_unescaped(self):
        html_body = (
            b"<html><head><style>.x{color:red}</style></head>"
            b"<body><script>alert('bad')</script>"
            b"<p>Hello &amp; welcome</p>   <p>visible text</p></body></html>"
        )
        fake = _FakeClient(
            response=_FakeResponse(
                content=html_body,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        )
        with patch("agent.mcp_server.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
            "agent.mcp_server.httpx.Client", return_value=fake
        ):
            result = fetch_url("http://example.com/page")
        self.assertTrue(result.startswith(BEGIN_MARKER))
        self.assertTrue(result.endswith(END_MARKER))
        self.assertIn("Hello & welcome", result)  # entities unescaped
        self.assertIn("visible text", result)
        self.assertNotIn("alert", result)  # <script> content dropped
        self.assertNotIn("color:red", result)  # <style> content dropped

    def test_truncation_to_max_chars(self):
        big = b"<html><body>" + b"A" * (MAX_RETURNED_CHARS + 5000) + b"</body></html>"
        fake = _FakeClient(
            response=_FakeResponse(content=big, headers={"content-type": "text/html"})
        )
        with patch("agent.mcp_server.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
            "agent.mcp_server.httpx.Client", return_value=fake
        ):
            result = fetch_url("http://example.com/big")
        inner = result[len(BEGIN_MARKER):].rsplit(END_MARKER, 1)[0].strip()
        self.assertLessEqual(len(inner), MAX_RETURNED_CHARS)

    def test_non_html_returned_as_raw_text(self):
        fake = _FakeClient(
            response=_FakeResponse(
                content=b'{"key": "value"}',
                headers={"content-type": "application/json"},
            )
        )
        with patch("agent.mcp_server.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
            "agent.mcp_server.httpx.Client", return_value=fake
        ):
            result = fetch_url("http://example.com/data.json")
        self.assertIn('{"key": "value"}', result)

    def test_non_http_scheme_blocked_without_request(self):
        with patch("agent.mcp_server.httpx.Client") as mock_client:
            result = fetch_url("ftp://example.com/x")
        self.assertTrue(result.startswith("Error:"))
        mock_client.assert_not_called()

    def test_internal_hosts_blocked_without_request(self):
        for url in (
            "http://localhost/x",
            "http://127.0.0.1/x",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/x",
            "http://192.168.1.1/x",
        ):
            with self.subTest(url=url):
                with patch("agent.mcp_server.httpx.Client") as mock_client:
                    result = fetch_url(url)
                self.assertTrue(result.startswith("Error:"), url)
                mock_client.assert_not_called()

    def test_hostname_resolving_to_private_ip_blocked(self):
        with patch(
            "agent.mcp_server.socket.getaddrinfo", return_value=_addrinfo("10.1.2.3")
        ), patch("agent.mcp_server.httpx.Client") as mock_client:
            result = fetch_url("http://sneaky.example.com/x")
        self.assertTrue(result.startswith("Error:"))
        mock_client.assert_not_called()

    def test_unresolvable_host_fails_closed(self):
        with patch(
            "agent.mcp_server.socket.getaddrinfo", side_effect=socket.gaierror("no such host")
        ), patch("agent.mcp_server.httpx.Client") as mock_client:
            result = fetch_url("http://does-not-exist.invalid/x")
        self.assertTrue(result.startswith("Error:"))
        mock_client.assert_not_called()

    def test_http_exception_becomes_error_string(self):
        fake = _FakeClient(exc=httpx.ConnectError("boom"))
        with patch("agent.mcp_server.socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO), patch(
            "agent.mcp_server.httpx.Client", return_value=fake
        ):
            result = fetch_url("http://example.com/x")
        self.assertTrue(result.startswith("Error:"))
        self.assertNotIn("Traceback", result)

    def test_redirect_to_internal_host_blocked(self):
        # The initial host is public but the final response.url resolves internal.
        fake = _FakeClient(
            response=_FakeResponse(
                content=b"<html><body>secret</body></html>",
                headers={"content-type": "text/html"},
                url="http://127.0.0.1/x",
            )
        )

        def _resolve(host, *args, **kwargs):
            return _PUBLIC_ADDRINFO if host == "example.com" else _addrinfo("127.0.0.1")

        with patch("agent.mcp_server.socket.getaddrinfo", side_effect=_resolve), patch(
            "agent.mcp_server.httpx.Client", return_value=fake
        ):
            result = fetch_url("http://example.com/redirects-internal")
        self.assertTrue(result.startswith("Error:"))
        self.assertNotIn("secret", result)


class ServerMountTests(unittest.TestCase):
    """MCP-01: the FastMCP server exposes fetch_url and a mountable ASGI app."""

    def test_fetch_url_is_registered(self):
        tools = asyncio.run(mcp_server.list_tools())
        self.assertIn("fetch_url", [tool.name for tool in tools])

    def test_streamable_http_app_is_callable(self):
        app = mcp_server.streamable_http_app()
        self.assertTrue(callable(app))


class ServerReachabilityTests(unittest.TestCase):
    """MCP-01: offline proxy for the A2 deploy smoke — the mounted /mcp route is
    registered before the SPA catch-all and answers a JSON-RPC request in-process.

    The live cross-instance smoke (Plan 05-02 Task 2) still requires a real deploy;
    this proves the mount wiring, combined lifespan, and Host-header handling work
    without a browser or Vercel.
    """

    def test_mount_precedes_spa_catchall(self):
        from unittest.mock import patch

        from starlette.routing import Mount

        with patch("agent.db.create_pool", side_effect=RuntimeError("no db")):
            import api
        routes = api.app.router.routes
        mcp_idx = next(
            i for i, r in enumerate(routes)
            if isinstance(r, Mount) and getattr(r, "path", "") == "/mcp"
        )
        catchall_idx = next(
            i for i, r in enumerate(routes) if getattr(r, "path", "") == "/{path:path}"
        )
        self.assertLess(mcp_idx, catchall_idx, "/mcp mount must precede the SPA catch-all")

    def test_mcp_endpoint_answers_jsonrpc_in_process(self):
        import json
        from unittest.mock import patch

        import httpx

        import api

        async def _smoke():
            transport = httpx.ASGITransport(app=api.app)
            init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
            # The reachable endpoint is /mcp/ (trailing slash); bare /mcp is
            # shadowed by the SPA catch-all. discover_mcp_tools() normalizes to this.
            async with api.app.router.lifespan_context(api.app):
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://localhost"
                ) as client:
                    return await asyncio.wait_for(
                        client.post("/mcp/", content=json.dumps(init), headers=headers),
                        timeout=10,
                    )

        with patch("agent.db.create_pool", side_effect=RuntimeError("no db")):
            response = asyncio.run(_smoke())
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        payload = response.json()
        self.assertEqual(payload.get("jsonrpc"), "2.0")
        self.assertIn("result", payload)


def _fake_fetch_tool(name="fetch_url"):
    def _run(url: str) -> str:
        return "ok"

    return StructuredTool.from_function(func=_run, name=name, description="fetch a url")


class DiscoveryGateTests(unittest.TestCase):
    """MCP-04: discovery is env-gated and degrades to ([], []) without raising."""

    def test_unset_returns_empty_and_builds_no_client(self):
        # If discovery is unset it must NOT construct a client — prove it by making
        # any construction raise, then asserting a clean empty result anyway.
        with patch.dict(os.environ, {"MCP_FETCH_SERVER_URL": ""}, clear=False), patch(
            "agent.mcp_client.MultiServerMCPClient", side_effect=AssertionError("must not construct")
        ) as mock_client:
            tools, schemas = run(discover_mcp_tools())
        self.assertEqual((tools, schemas), ([], []))
        mock_client.assert_not_called()

    def test_unreachable_server_degrades_without_raising(self):
        mock_instance = MagicMock()
        mock_instance.get_tools = AsyncMock(side_effect=ConnectionError("refused"))
        with patch.dict(
            os.environ, {"MCP_FETCH_SERVER_URL": "http://127.0.0.1:1/mcp"}, clear=False
        ), patch("agent.mcp_client.MultiServerMCPClient", return_value=mock_instance):
            tools, schemas = run(discover_mcp_tools())
        self.assertEqual((tools, schemas), ([], []))


class DiscoveryTests(unittest.TestCase):
    """MCP-02: a reachable server yields BaseTools plus convert_to_openai_tool schemas."""

    def test_discovers_tool_and_builds_schema(self):
        fake = _fake_fetch_tool("fetch_url")
        mock_instance = MagicMock()
        mock_instance.get_tools = AsyncMock(return_value=[fake])
        with patch.dict(
            os.environ, {"MCP_FETCH_SERVER_URL": "https://example.com/mcp"}, clear=False
        ), patch("agent.mcp_client.MultiServerMCPClient", return_value=mock_instance):
            tools, schemas = run(discover_mcp_tools())
        self.assertEqual([tool.name for tool in tools], ["fetch_url"])
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["function"]["name"], "fetch_url")

    def test_trailing_slash_added_to_configured_url(self):
        # A URL configured as ".../mcp" is normalized to ".../mcp/" (the reachable path).
        captured = {}

        def _capture(config):
            captured["url"] = config["fetch"]["url"]
            instance = MagicMock()
            instance.get_tools = AsyncMock(return_value=[])
            return instance

        with patch.dict(
            os.environ, {"MCP_FETCH_SERVER_URL": "https://example.com/mcp"}, clear=False
        ), patch("agent.mcp_client.MultiServerMCPClient", side_effect=_capture):
            run(discover_mcp_tools())
        self.assertEqual(captured["url"], "https://example.com/mcp/")


if __name__ == "__main__":
    unittest.main()
