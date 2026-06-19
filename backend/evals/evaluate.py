"""Agent evaluation harness.

Runs the real LangGraph agent against a labelled dataset and scores two
dimensions that matter for a tool-using agent:

- Task success: did the final answer satisfy the case's checks?
- Tool selection: did the agent use the expected tool(s)?

Usage (from backend/):
    python -m evals.evaluate                 # full suite
    python -m evals.evaluate --category math # one category
    python -m evals.evaluate --offline       # skip live web_search cases
    python -m evals.evaluate --threshold 0.8 # exit non-zero below this success rate

Results are written to evals/results.json and evals/results.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph import build_graph  # noqa: E402
from agent.llms import configured_model_info, load_model_environment  # noqa: E402
from agent.state import MaxIterationsError  # noqa: E402

CASES_PATH = Path(__file__).with_name("cases.jsonl")
RESULTS_JSON = Path(__file__).with_name("results.json")
RESULTS_MD = Path(__file__).with_name("results.md")
BASELINE_JSON = Path(__file__).with_name("baseline.json")

NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def load_cases() -> list[dict]:
    cases: list[dict] = []
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("//"):
            cases.append(json.loads(stripped))
    return cases


def _numbers(text: str) -> list[float]:
    values: list[float] = []
    for token in NUMBER_RE.findall(text):
        try:
            values.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return values


def check_answer(answer: str, check: dict) -> bool:
    kind = check["type"]
    lowered = answer.lower()
    if kind == "numeric":
        target = float(check["value"])
        tolerance = float(check.get("tol", 1e-6))
        return any(abs(value - target) <= tolerance for value in _numbers(answer))
    if kind == "contains_all":
        return all(needle.lower() in lowered for needle in check["values"])
    if kind == "contains_any":
        return any(needle.lower() in lowered for needle in check["values"])
    if kind == "regex":
        return re.search(check["pattern"], answer, flags=re.IGNORECASE) is not None
    raise ValueError(f"unknown check type: {kind}")


def _initial_state(query: str) -> dict:
    return {
        "messages": [HumanMessage(content=query)],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }


def _tools_used(final_state: dict) -> list[str]:
    steps = final_state.get("intermediate_steps", [])
    return list(dict.fromkeys(s["action"] for s in steps if s.get("action")))


def evaluate_tool_selection(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return actual == []
    return all(tool in actual for tool in expected)


def run_case(graph, case: dict) -> dict:
    started = time.perf_counter()
    error = None
    answer = ""
    tools: list[str] = []
    try:
        final_state = graph.invoke(_initial_state(case["query"]))
        answer = final_state.get("final_answer") or ""
        tools = _tools_used(final_state)
    except MaxIterationsError as exc:
        error = f"MaxIterationsError: {exc}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a failed case
        error = f"{type(exc).__name__}: {exc}"

    checks = case.get("checks", [])
    answer_pass = error is None and all(check_answer(answer, c) for c in checks)
    tool_pass = error is None and evaluate_tool_selection(
        case.get("expect_tools", []), tools
    )

    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expect_tools": case.get("expect_tools", []),
        "tools_used": tools,
        "answer": answer,
        "answer_pass": answer_pass,
        "tool_pass": tool_pass,
        "error": error,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def summarize(results: list[dict]) -> dict:
    total = len(results)
    answer_pass = sum(1 for r in results if r["answer_pass"])
    tool_pass = sum(1 for r in results if r["tool_pass"])
    categories: dict[str, dict] = {}
    for r in results:
        bucket = categories.setdefault(
            r["category"], {"total": 0, "answer_pass": 0, "tool_pass": 0}
        )
        bucket["total"] += 1
        bucket["answer_pass"] += int(r["answer_pass"])
        bucket["tool_pass"] += int(r["tool_pass"])
    return {
        "total": total,
        "answer_pass": answer_pass,
        "tool_pass": tool_pass,
        "task_success_rate": round(answer_pass / total, 4) if total else 0.0,
        "tool_selection_rate": round(tool_pass / total, 4) if total else 0.0,
        "by_category": categories,
    }


def _pct(passed: int, total: int) -> str:
    return f"{passed}/{total} ({round(100 * passed / total) if total else 0}%)"


def render_table(results: list[dict], summary: dict) -> str:
    lines = [
        "Agent Evaluation Results",
        "=" * 64,
        f"Task success:    {_pct(summary['answer_pass'], summary['total'])}",
        f"Tool selection:  {_pct(summary['tool_pass'], summary['total'])}",
        "",
        "By category:",
    ]
    for name, bucket in sorted(summary["by_category"].items()):
        lines.append(
            f"  {name:<8} answer {_pct(bucket['answer_pass'], bucket['total'])}"
            f"   tool {_pct(bucket['tool_pass'], bucket['total'])}"
        )
    failures = [r for r in results if not r["answer_pass"] or not r["tool_pass"]]
    if failures:
        lines += ["", "Failures:"]
        for r in failures:
            reason = r["error"] or (
                f"answer_pass={r['answer_pass']} tool_pass={r['tool_pass']} "
                f"(expected {r['expect_tools']}, used {r['tools_used']})"
            )
            lines.append(f"  [{r['id']}] {reason}")
            if not r["error"]:
                lines.append(f"      answer: {r['answer'][:120]!r}")
    return "\n".join(lines)


def write_baseline(results: list[dict], summary: dict, generated_at: str) -> None:
    """Write the published, frontend-facing baseline. Trimmed to per-case
    pass/fail (no full answers) plus the active model, so it is safe to commit
    and serve at /evals."""
    models = configured_model_info()
    active = models[0] if models else None
    BASELINE_JSON.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "model": (
                    {"provider": active.provider_label, "label": active.label}
                    if active
                    else None
                ),
                "summary": summary,
                "cases": [
                    {
                        "id": r["id"],
                        "category": r["category"],
                        "answer_pass": r["answer_pass"],
                        "tool_pass": r["tool_pass"],
                        "latency_ms": r["latency_ms"],
                    }
                    for r in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_markdown(results: list[dict], summary: dict, generated_at: str) -> None:
    rows = ["| id | category | answer | tool | latency |", "|----|----------|--------|------|---------|"]
    for r in results:
        rows.append(
            f"| {r['id']} | {r['category']} | "
            f"{'PASS' if r['answer_pass'] else 'FAIL'} | "
            f"{'PASS' if r['tool_pass'] else 'FAIL'} | {r['latency_ms']}ms |"
        )
    md = (
        f"# Agent Evaluation Results\n\n"
        f"_Generated {generated_at}_\n\n"
        f"- **Task success:** {_pct(summary['answer_pass'], summary['total'])}\n"
        f"- **Tool selection:** {_pct(summary['tool_pass'], summary['total'])}\n\n"
        + "\n".join(rows)
        + "\n"
    )
    RESULTS_MD.write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the agent evaluation suite.")
    parser.add_argument("--category", help="only run cases in this category")
    parser.add_argument(
        "--offline", action="store_true", help="skip live web_search cases"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="seconds between cases (rate limits)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="exit non-zero if task success rate is below this",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="also write evals/baseline.json (committed, served at /evals)",
    )
    args = parser.parse_args()

    load_model_environment()
    cases = load_cases()
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if args.offline:
        cases = [c for c in cases if c["category"] != "web"]
    if not cases:
        print("No cases matched the filters.")
        return 1

    graph = build_graph()
    results: list[dict] = []
    for index, case in enumerate(cases):
        result = run_case(graph, case)
        results.append(result)
        status = "ok " if result["answer_pass"] and result["tool_pass"] else "FAIL"
        print(f"[{status}] {result['id']:<10} {result['latency_ms']:>6}ms")
        if args.delay and index < len(cases) - 1:
            time.sleep(args.delay)

    summary = summarize(results)
    generated_at = datetime.now(timezone.utc).isoformat()
    RESULTS_JSON.write_text(
        json.dumps(
            {"generated_at": generated_at, "summary": summary, "results": results},
            indent=2,
        ),
        encoding="utf-8",
    )
    write_markdown(results, summary, generated_at)
    if args.publish:
        write_baseline(results, summary, generated_at)

    print("\n" + render_table(results, summary))
    written = f"{RESULTS_JSON.name} and {RESULTS_MD.name}"
    if args.publish:
        written += f" and {BASELINE_JSON.name}"
    print(f"\nResults written to {written}")

    return 1 if summary["task_success_rate"] < args.threshold else 0


if __name__ == "__main__":
    raise SystemExit(main())
