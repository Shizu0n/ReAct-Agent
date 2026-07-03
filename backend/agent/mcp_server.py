"""Companion MCP server: a single real, hardened tool the agent can discover.

Exposes a FastMCP instance (`mcp_server`) with one tool, `fetch_url`, mounted
into the main FastAPI app at /mcp in Plan 05-02. Built with `stateless_http=True`
so no server-side session must survive across Vercel serverless instances, and
`streamable_http_path="/"` so a later `app.mount("/mcp", ...)` reaches /mcp rather
than double-nesting to /mcp/mcp.

`fetch_url` is hardened from the first commit: SSRF host/scheme filtering, byte and
character caps, prompt-injection delimiter wrapping, and the repo's
"return an Error: string, never raise" tool convention.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from agent.ingest import strip_invisible

# DNS-rebinding protection defaults ON with an empty allowed_hosts list, which
# rejects EVERY Host header (including the deployed Vercel domain) with HTTP 421.
# That protection guards local/stdio servers from browser-driven rebinding; it is
# pointless here — this server is public, stateless, and exposes only a read-only,
# SSRF-hardened tool — and it would block the agent from calling its own /mcp route.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)

mcp_server = FastMCP(
    "react-agent-tools",
    stateless_http=True,
    json_response=True,
    transport_security=_TRANSPORT_SECURITY,
)
# FastMCP's own default streamable_http_path is "/mcp"; mounting at
# app.mount("/mcp", ...) would then double-nest to an unreachable /mcp/mcp.
# Set it to "/" so the reachable route stays /mcp (05-RESEARCH.md Pitfall 2).
mcp_server.settings.streamable_http_path = "/"

MAX_FETCH_BYTES = 500_000
MAX_RETURNED_CHARS = 4000
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 10

BEGIN_MARKER = "--- BEGIN FETCHED PAGE ---"
END_MARKER = "--- END FETCHED PAGE ---"


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping <script>/<style> content."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


def _host_is_blocked(hostname: str) -> bool:
    """Return True if hostname is localhost or resolves to a non-public address.

    Fails closed: an unresolvable host is treated as blocked. Resolving every
    address the host maps to blocks literal internal IPs (127.*, 10.*,
    172.16-31.*, 192.168.*, 169.254.* cloud metadata) and DNS names that point
    at them.
    """
    if hostname.lower() == "localhost":
        return True
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return True  # fail closed on resolution failure
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


def _ssrf_guard(url: str) -> str | None:
    """Return an 'Error: ...' string if url is unsafe to fetch, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Error: only http:// and https:// URLs are supported."
    if not parsed.hostname:
        return "Error: URL has no host."
    if _host_is_blocked(parsed.hostname):
        return "Error: refusing to fetch an internal or non-public host."
    return None


@mcp_server.tool()
def fetch_url(url: str) -> str:
    """Fetch a web page by URL and return its readable text content.

    Args:
        url: An http:// or https:// URL to fetch. Internal, private, loopback,
            and link-local hosts are refused (SSRF protection).

    Returns:
        The page's visible text (scripts/styles removed, whitespace collapsed,
        HTML entities unescaped), wrapped between "--- BEGIN FETCHED PAGE ---"
        and "--- END FETCHED PAGE ---" and truncated. On any failure — a blocked
        host, a network/HTTP error — returns an "Error: ..." string instead of
        raising.
    """
    blocked = _ssrf_guard(url)
    if blocked is not None:
        return blocked

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            max_redirects=MAX_REDIRECTS,
        ) as client:
            response = client.get(
                url, headers={"User-Agent": "react-agent-mcp-fetch/1.0"}
            )
            response.raise_for_status()

        # follow_redirects could have been steered to an internal host; re-check
        # the final URL's host before returning any content (defense in depth).
        final_blocked = _ssrf_guard(str(response.url))
        if final_blocked is not None:
            return final_blocked

        body = response.content[:MAX_FETCH_BYTES]
        decoded = body.decode(response.encoding or "utf-8", errors="replace")
        if "text/html" in response.headers.get("content-type", ""):
            extractor = _TextExtractor()
            extractor.feed(decoded)
            text = html.unescape(extractor.text())
        else:
            text = decoded
        text = strip_invisible(text).strip()
    except Exception as exc:
        return f"Error: fetch failed: {type(exc).__name__}: {exc}"

    if not text:
        return "No text content found at this URL."
    return f"{BEGIN_MARKER}\n{text[:MAX_RETURNED_CHARS]}\n{END_MARKER}"
