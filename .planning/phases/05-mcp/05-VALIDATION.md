---
phase: 5
slug: mcp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `05-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (backend); no frontend test framework — MCP-03 trace parity confirmed to need zero frontend changes (`ReasoningPanel`/`useAgent` render `Step` generically) |
| **Config file** | none — discovery via `-s tests` |
| **Quick run command** | `python -m unittest tests.test_mcp -v` (new module) |
| **Full suite command** | `python -m unittest discover -s tests -v` (run from `backend/`) |
| **Estimated runtime** | ~20–40 seconds (current suite ~105 tests) |

*No live MCP server or external network in unit tests: patch `MultiServerMCPClient` with a stubbed async `get_tools()` (mirrors `test_memory.py`'s `FakeStore` pattern); feed a static HTML string / mock `httpx` for `fetch_url`. Reuse the `REACT_AGENT_DISABLE_WEB_SEARCH_GATE=1` env-var-patching style for `MCP_FETCH_SERVER_URL`.*

---

## Sampling Rate

- **After every task commit:** Run `python -m unittest tests.test_mcp -v` (or the touched module's test)
- **After every plan wave:** Run `python -m unittest discover -s tests -v` (from `backend/`)
- **Before `/gsd-verify-work`:** Full suite green **plus** a manual prod-like check (Assumption A2): deploy, point `MCP_FETCH_SERVER_URL` at the deployed `/mcp` route, and confirm two requests spaced far enough apart to plausibly hit different warm instances both succeed
- **Max feedback latency:** ~40 seconds

---

## Per-Task Verification Map

| Requirement | Wave | Behavior (observable signal) | Test Type | Automated Command | File Exists | Status |
|-------------|------|------------------------------|-----------|-------------------|-------------|--------|
| MCP-04 | 1 | `MCP_FETCH_SERVER_URL` unset → `discover_mcp_tools()` returns `([], [])` with zero network calls (no mock server started) | unit | `python -m unittest tests.test_mcp.DiscoveryGateTests -v` | ❌ W0 | ⬜ pending |
| MCP-04 | 1 | `MCP_FETCH_SERVER_URL` set but unreachable (closed port) → returns `([], [])`, no exception propagates | unit | `python -m unittest tests.test_mcp.DiscoveryGateTests.test_unreachable_degrades -v` | ❌ W0 | ⬜ pending |
| MCP-02 | 1 | Given a fake `MultiServerMCPClient.get_tools()` returning a `BaseTool`, `discover_mcp_tools()` returns it plus a matching OpenAI-style schema dict (`convert_to_openai_tool` shape) | unit (patch `MultiServerMCPClient`) | `python -m unittest tests.test_mcp.DiscoveryTests -v` | ❌ W0 | ⬜ pending |
| MCP-01 | 1 | `fetch_url` returns extracted text for a fixed local HTML fixture (no live network) | unit (static HTML / mock `httpx.Client.get`) | `python -m unittest tests.test_mcp.FetchToolTests -v` | ❌ W0 | ⬜ pending |
| MCP-01 | 1 (or 2) | `GET/POST /mcp` (mounted app) responds to a `tools/list` JSON-RPC request with the `fetch_url` tool listed | integration (TestClient against mounted sub-app; `tools/list` doesn't invoke the tool) | `python -m unittest tests.test_mcp.ServerMountTests -v` | ❌ W0 | ⬜ pending |
| MCP-03 | 2 | `tool_node`, given an AI message whose tool call names a fake MCP tool, produces a `Step` with the same keys (`thought`, `action`, `action_input`, `observation`, `timestamp`, `elapsed_ms`) as a native tool call | unit (fake `BaseTool` with `.ainvoke`) | `python -m unittest tests.test_graph.McpToolNodeTests -v` | ❌ W0 (extend `test_graph.py`, `StepTimingTests` style) | ⬜ pending |
| MCP-03 | 2 | An MCP tool execution error is caught and returned as an `"Error: ..."` observation string, not raised | unit | `python -m unittest tests.test_graph.McpToolNodeTests.test_mcp_tool_error_becomes_observation -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_mcp.py` — discovery gating (unset/unreachable), schema conversion, server mount `tools/list`, `fetch_url` extraction — all NEW (mirrors `test_memory.py`'s `FakeStore`-style fixture: a `FakeMCPTool`/patched `MultiServerMCPClient` with a stubbed async `get_tools()`, no live server or network)
- [ ] `backend/tests/test_graph.py` `McpToolNodeTests` — extend existing file, same `StepTimingTests` style (fake `AIMessage` with a tool call, assert `Step` shape)
- [ ] Test fixture: a fake `BaseTool` subclass or `langchain_core.tools.StructuredTool.from_function` wrapping an async no-op, used in place of a real MCP-discovered tool

*Reuse the existing env-var-patching style (`patch.dict(os.environ, ...)`) for `MCP_FETCH_SERVER_URL` in the gating tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent discovers and invokes a real MCP tool in a live conversation | MCP-01, MCP-02 (SC1) | Requires a live LLM provider + the deployed `/mcp` route; not reproducible in offline unit tests | With `MCP_FETCH_SERVER_URL` set, ask the agent a question that requires fetching a URL; confirm a real `fetch_url` MCP tool call executes and the answer uses fetched content |
| MCP tool call renders identically to native tool calls in the trace panel | MCP-03 (SC2) | No frontend test framework | QA: run a query that triggers the MCP tool; open the reasoning panel and confirm the MCP call shows the same thought/action/observation structure and visual treatment as `web_search`/`calculator` |
| Agent starts and responds normally with `MCP_FETCH_SERVER_URL` unset | MCP-04 (SC3) | End-to-end startup + response behavior; unit test covers the gate, live check confirms no user-visible degradation | Unset the env var, start the app, run a normal query; confirm no error banner, no added latency |
| Mounted `/mcp` route survives Vercel cross-instance traffic | MCP-01 (Assumption A2) | Serverless cold-start / concurrent-instance behavior of `stateless_http=True` not reproducible in unit tests | Deploy preview; `curl` the `/mcp` `tools/list` twice with enough spacing to plausibly hit different warm instances; confirm both succeed. **Recommend an early smoke-test task before deep build-out.** |
| README documents the MCP architecture with a diagram | MCP-05 (SC4) | Documentation/visual check | Confirm README contains an architecture diagram of the MCP integration (agent ↔ client ↔ HTTP ↔ server) |

---

## Security Domain (ASVS L1, `security_block_on: high`)

New surfaces this phase introduces: an inbound HTTP route (mounted `/mcp`) and an outbound HTTP call (`fetch_url` reaching arbitrary third-party URLs).

- **V5 Input Validation (SSRF via `fetch_url`)** — `url` is model-controlled input reaching an outbound `httpx` GET. Restrict to `http(s)://` schemes; **planner must scope** blocking of internal hostnames/IP ranges (`localhost`, `127.*`, `169.254.*`, `10.*`, `172.16–31.*`, `192.168.*`) as a defense-in-depth task (not yet in the research Code Example).
- **Prompt injection via fetched page content** — wrap untrusted fetched content in the existing delimiter barrier + system-prompt instruction, mirroring the RAG-09 / `memory_read` pattern.
- **V7 Error Handling** — `fetch_url` + MCP transport errors caught and returned as observation strings (established pattern), never raised as raw stack traces; `redact_secrets` continues to apply to logged exceptions.
- **DoS caps** — `MAX_FETCH_BYTES` / `MAX_RETURNED_CHARS` on `fetch_url`; explicit `timeout` on `MultiServerMCPClient` connection config and the `httpx` client (mirrors `web_search` caps).

---

## Validation Sign-Off

- [ ] All backend tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter (by planner/checker once mapped)

**Approval:** pending
