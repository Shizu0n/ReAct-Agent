from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from agent.state import Step
from agent.tools import calculator, python_executor


@dataclass(frozen=True)
class ShortcutResult:
    final_answer: str
    step: Step


EXTERNAL_INTENT_WORDS = (
    "current",
    "latest",
    "news",
    "recent",
    "search",
    "trends",
    "web",
)
MATH_INTENT_WORDS = (
    "calculate",
    "compute",
    "solve",
    "what is",
)
STATS_INTENT_WORDS = (
    "mean",
    "median",
    "standard deviation",
    "std",
)
EXPLAIN_INTENT_WORDS = (
    "demonstrate",
    "explain",
    "show work",
    "step",
    "steps",
)


def try_shortcut(query: str) -> ShortcutResult | None:
    normalized_query = _normalize_text(query)
    if not normalized_query or _has_external_intent(normalized_query):
        return None

    return (
        _try_compound_growth(query, normalized_query)
        or _try_statistics(query, normalized_query)
        or _try_square_root(query, normalized_query)
        or _try_arithmetic(query, normalized_query)
    )


def try_contextual_shortcut(query: str, history: list[str]) -> ShortcutResult | None:
    normalized_query = _normalize_text(query)
    if not _is_explanation_followup(normalized_query):
        return None

    for previous in reversed(history[-8:]):
        value = _extract_square_root_value(previous, _normalize_text(previous))
        if value is not None:
            return _square_root_shortcut(value, explain=True)

    return None


def _has_external_intent(normalized_query: str) -> bool:
    return any(word in normalized_query for word in EXTERNAL_INTENT_WORDS)


def _normalize_text(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _new_step(thought: str, action: str, action_input: str, observation: str) -> Step:
    return {
        "thought": thought,
        "action": action,
        "action_input": action_input,
        "observation": observation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _try_compound_growth(query: str, normalized_query: str) -> ShortcutResult | None:
    if not any(
        word in normalized_query for word in ("compound", "growth", "juros", "invest")
    ):
        return None

    match = re.search(
        r"(?:\$|usd\s*)?(?P<principal>\d[\d,]*(?:\.\d+)?)"
        r".{0,80}?(?P<rate>\d+(?:\.\d+)?)\s*%"
        r".{0,80}?(?P<years>\d+(?:\.\d+)?)\s*(?:years?|anos?)",
        query,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    principal = float(match.group("principal").replace(",", ""))
    rate = float(match.group("rate"))
    years = float(match.group("years"))
    value = principal * (1 + rate / 100) ** years
    years_label = str(int(years)) if years.is_integer() else str(years)
    expression = f"{principal:g} * (1 + {rate:g} / 100) ** {years:g}"
    answer = f"The investment grows to about ${value:,.2f} after {years_label} years."
    return ShortcutResult(
        final_answer=answer,
        step=_new_step(
            "Use deterministic compound-interest math; no LLM needed.",
            "calculator",
            expression,
            answer,
        ),
    )


def _try_statistics(query: str, normalized_query: str) -> ShortcutResult | None:
    if not any(word in normalized_query for word in STATS_INTENT_WORDS):
        return None

    match = re.search(r"\[([^\]]+)\]", query)
    if not match:
        return None

    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", match.group(1))]
    if len(numbers) < 2:
        return None

    parts: list[str] = []
    if "mean" in normalized_query:
        parts.append(f"mean: {_format_number(statistics.mean(numbers))}")
    if "median" in normalized_query:
        parts.append(f"median: {_format_number(statistics.median(numbers))}")
    if (
        "standard deviation" in normalized_query
        or "std" in normalized_query
    ):
        parts.append(
            f"sample standard deviation: {_format_number(statistics.stdev(numbers))}"
        )
        parts.append(
            f"population standard deviation: {_format_number(statistics.pstdev(numbers))}"
        )
    if not parts:
        return None

    answer = "; ".join(parts) + "."
    code = f"print({answer!r})"
    return ShortcutResult(
        final_answer=answer,
        step=_new_step(
            "Use local Python statistics; no LLM needed.",
            "python_executor",
            code,
            python_executor.invoke({"code": f"print({answer!r})"}),
        ),
    )


def _try_square_root(query: str, normalized_query: str) -> ShortcutResult | None:
    value = _extract_square_root_value(query, normalized_query)
    if value is None:
        return None

    return _square_root_shortcut(value, explain=_wants_explanation(normalized_query))


def _square_root_shortcut(value: float, explain: bool) -> ShortcutResult | None:
    expression = f"math.sqrt({value:g})"
    result = str(calculator.invoke({"expression": expression}))
    if result.startswith("Error:"):
        return None

    root = float(result)
    root_label = _format_number(root)
    value_label = _format_number(value)
    radical = f"√{value_label}"

    if explain:
        if root.is_integer() and value >= 0:
            answer = (
                f"{radical} = {root_label}.\n\n"
                "Steps:\n"
                f"1. A square root asks which number multiplied by itself gives {value_label}.\n"
                f"2. {root_label} × {root_label} = {value_label}.\n"
                f"3. Therefore, {radical} = {root_label}."
            )
        else:
            answer = (
                f"{radical} ≈ {root_label}.\n\n"
                "Steps:\n"
                f"1. Rewrite the request as {expression}.\n"
                f"2. Evaluate it with the calculator tool.\n"
                f"3. The result is approximately {root_label}."
            )
    else:
        answer = f"{radical} = {root_label}."

    return ShortcutResult(
        final_answer=answer,
        step=_new_step(
            "Use deterministic square-root math; no LLM needed.",
            "calculator",
            expression,
            answer,
        ),
    )


def _try_arithmetic(query: str, normalized_query: str) -> ShortcutResult | None:
    expression = _extract_arithmetic_expression(query, normalized_query)
    if expression is None:
        return None

    result = str(calculator.invoke({"expression": expression}))
    if result.startswith("Error:"):
        return None

    return ShortcutResult(
        final_answer=result,
        step=_new_step(
            "Use deterministic calculator; no LLM needed.",
            "calculator",
            expression,
            result,
        ),
    )


def _extract_arithmetic_expression(query: str, normalized_query: str) -> str | None:
    has_math_intent = any(word in normalized_query for word in MATH_INTENT_WORDS)
    normalized = query.replace("\u00d7", "*").replace("\u00f7", "/").replace("^", "**")
    normalized = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " * ", normalized)
    normalized = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", normalized)

    if not has_math_intent and not re.fullmatch(
        r"[\d\s.,()+\-*/%*]+[?.!]?", normalized.strip()
    ):
        return None

    candidates = re.findall(r"\d[\d\s.,()+\-*/%*]*\d", normalized)
    for candidate in candidates:
        expression = candidate.strip(" .,;:?!")
        if _has_binary_operator(expression):
            return expression
    return None


def _extract_square_root_value(query: str, normalized_query: str) -> float | None:
    match = re.search(r"√\s*(?P<value>-?\d+(?:\.\d+)?)", query)
    if match:
        return float(match.group("value"))

    match = re.search(
        r"\bsqrt\s*\(\s*(?P<value>-?\d+(?:\.\d+)?)\s*\)", normalized_query
    )
    if match:
        return float(match.group("value"))

    match = re.search(
        r"\bsquare root of\s+(?P<value>-?\d+(?:\.\d+)?)", normalized_query
    )
    if match:
        return float(match.group("value"))

    return None


def _wants_explanation(normalized_query: str) -> bool:
    return any(word in normalized_query for word in EXPLAIN_INTENT_WORDS)


def _is_explanation_followup(normalized_query: str) -> bool:
    followup_terms = (
        "explain more",
        "more details",
        "more steps",
        "show the steps",
        "the steps",
        "step by step",
    )
    return any(term in normalized_query for term in followup_terms)


def _has_binary_operator(expression: str) -> bool:
    if any(operator in expression for operator in ("+", "*", "/", "%")):
        return True
    return expression.count("-") == 1 and bool(re.search(r"\d\s*-\s*\d", expression))


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
