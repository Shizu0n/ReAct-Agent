# Agent Evaluation Harness

Measures whether the ReAct agent actually works, on two axes that matter for a
tool-using agent:

- **Task success** — did the final answer satisfy the case's checks?
- **Tool selection** — did the agent use the expected tool (or correctly use no
  tool for direct-answer questions)?

Unit tests (`backend/tests/`) verify components in isolation with scripted LLMs.
These evals run the **real** LangGraph agent against the **real** model fallback
chain, so they catch behavior that only emerges end to end — wrong tool choice,
unexecuted code, over-eager web search.

## Run

```bash
cd backend
python -m evals.evaluate                 # full suite (all categories)
python -m evals.evaluate --category math  # one category
python -m evals.evaluate --offline        # skip live web_search cases
python -m evals.evaluate --delay 3        # seconds between cases (rate limits)
python -m evals.evaluate --threshold 0.8  # exit non-zero below this success rate
python -m evals.evaluate --publish        # also write the committed baseline.json
```

Results are written to `evals/results.json` (machine-readable) and
`evals/results.md` (table). Both are git-ignored run artifacts.

## Publishing the frontend baseline

`--publish` additionally writes `evals/baseline.json` — a trimmed, committed
summary (per-case pass/fail plus the active model, no full answers). The API
serves it at `GET /evals`, and the About page renders it under "How it scores".
Until a baseline is committed, the endpoint returns `{"status": "unavailable"}`
and the section shows a "baseline pending" state. To publish: run the full
suite when a provider's quota is healthy, then commit `baseline.json` and
redeploy.

## Dataset

`cases.jsonl`, one case per line:

```json
{"id": "math-001", "category": "math", "query": "What is 17 * 23 + sqrt(1764)?",
 "expect_tools": ["calculator"], "checks": [{"type": "numeric", "value": 433}]}
```

Categories: `math`, `code`, `web`, `direct` (no tool expected), `edge`.
Check types: `numeric` (with optional `tol`), `contains_all`, `contains_any`,
`regex`. `expect_tools: []` asserts the agent answered directly without a tool.
Several cases are tagged as regressions for bugs found during QA (the dropped
`17 * 23` term; unexecuted Fibonacci code).

## Free-tier quota constraint

The default providers are free tiers (Gemini 2.5 Flash → Groq → GitHub Models).
Gemini's free tier caps generate-content requests per day; a full 22-case run
issues 50+ model calls and can exhaust the daily quota.
Practical guidance:

- Run `--offline` or a single `--category` for quick checks.
- Use `--delay 3` (or higher) for full runs to stay under per-minute limits.
- These evals are a **periodic manual baseline**, not a per-commit CI gate. CI
  runs the deterministic unit tests. Regenerate the baseline when quota allows.

## Baseline finding

The first run surfaced a clear, fixable gap the unit tests missed: **task
accuracy is high, but tool-selection is weak** — the agent frequently answers
arithmetic and short code tasks from its own reasoning instead of calling the
calculator / python_executor. That is correct-but-not-inspectable, which
undercuts the point of a tool-using agent. It is the motivation for migrating
the agent to native function calling.
