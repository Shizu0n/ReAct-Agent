# Testing

**Analysis Date:** 2026-06-29

## Frameworks

### Backend (Python)

- **Unit tests:** Python standard library `unittest` (no pytest). Test discovery via `unittest discover`.
- **Mocking:** `unittest.mock.patch` plus hand-rolled fakes (`ScriptedLLM`, `CapturingLLM`, `FakeGraph`) — no `responses`/`httpx-mock` library.
- **API tests:** `fastapi.testclient.TestClient` (Starlette test client) for in-process HTTP against the FastAPI app.
- **Eval harness (separate from unit tests):** Custom runner in `backend/evals/evaluate.py` — exercises the *real* agent against *real* providers. This is a periodic manual baseline, **not** part of the unit suite and **not** a CI gate (it burns free-tier quota).

### Frontend (TypeScript/React)

- **No test framework configured.** `frontend/package.json` has no `test` script and no Vitest/Jest/Testing-Library dependency. Frontend correctness is covered only by `tsc -b` (type-check, part of `npm run build`) and ESLint. This is a coverage gap (see CONCERNS.md).

## Test Locations

```
backend/tests/
  test_agent.py        (~22 KB) — tools + agent graph behavior
  test_api.py          (~12 KB) — FastAPI endpoints via TestClient
  test_llms.py         (~10 KB) — provider fallback / model selection
  test_redaction.py    (~1.6 KB) — secret redaction logging
  test_suggestions.py  (~3 KB)  — /suggestions endpoint

backend/evals/         — eval harness, NOT unit tests
  evaluate.py          — runner
  cases.jsonl          — dataset (one JSON case per line)
  baseline.json        — committed trimmed summary (served at GET /evals)
  results.json / results.md — last run output
```

Test files mirror the module they exercise: `test_agent.py` → `agent/graph.py` + `agent/tools.py`, `test_api.py` → `api.py`, `test_llms.py` → `agent/llms.py`, `test_redaction.py` → `agent/redaction.py`.

## Running Tests

All commands run from `backend/` (so `agent` resolves as a top-level package).

```bash
# Full unit suite
python -m unittest discover -s tests -v

# Single file
python -m unittest tests.test_agent -v

# Single case
python -m unittest tests.test_agent.ToolTests.test_calculator_evaluates_math_expression

# Eval harness (real providers, manual baseline — not CI)
python -m evals.evaluate                 # all cases
python -m evals.evaluate --offline       # skip web cases
python -m evals.evaluate --category math
python -m evals.evaluate --publish       # rewrite committed baseline.json
```

## Test Structure & Patterns

**Class naming:** `<Feature>Tests` suffix (e.g., `ToolTests`, `SecretRedactionTests`, `LlmSelectionTests`) — consistent with the convention in CONVENTIONS.md.

**Scripted LLM fakes** — the agent is tested deterministically without provider calls. A `ScriptedLLM` yields a pre-baked sequence of `AIMessage`s (including native `tool_calls`):

```python
def make_tool_call(name, call_id="call-1", **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])

class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)
    def invoke(self, messages, tools=None):
        response = next(self._responses)
        return response if isinstance(response, AIMessage) else AIMessage(content=response)
```

`CapturingLLM` extends this to record the messages it received (for asserting prompt contents). `FakeGraph` (in `test_api.py`) stubs the whole graph — implementing both `invoke()` and `stream()` — so API tests don't build a real `StateGraph`.

**Tool tests** invoke LangChain tools directly via `.invoke({...})` and assert on the string result, including security-boundary cases (e.g., `calculator` rejecting `__import__`, `python_executor` capturing stdout). These guard the `python_executor` AST/import/builtin restrictions — do not loosen them to make a case pass.

**API tests** use `TestClient` with a patched/fake graph and assert on JSON shape and status codes.

## Test Configuration & Env

- **Web-search gate disabled in tests:** tests set `REACT_AGENT_DISABLE_WEB_SEARCH_GATE=1` so the `_requires_web_search` guardrail in `agent_node` does not force `web_search` calls during deterministic runs.
- **No API keys needed for unit tests** — all provider/network paths are faked. (Keys are only required for the live eval harness and the running server.)
- No `conftest.py`, no fixtures framework, no coverage tool (`coverage.py`/`pytest-cov`) configured — coverage is not measured.

## Coverage Assessment

**Covered well:**
- Tool execution + security boundaries (`calculator`, `python_executor`)
- Provider fallback / model selection (`llms.py`)
- Secret redaction
- Core API endpoints + SSE streaming shape
- `/suggestions` endpoint

**Gaps / risks:**
- **No frontend tests** at all (only type-check + lint).
- Unit suite relies on scripted fakes, so real provider-integration regressions surface only in the manual eval harness — which is not automated/gated.
- No measured coverage metric.

---

*Testing analysis: 2026-06-29*
