import ast
import contextlib
import io
import json
import math
import os
import re
from typing import Any

from langchain_core.tools import tool
from tavily import TavilyClient

DEFAULT_TAVILY_MAX_RESULTS = 2
DEFAULT_TAVILY_SNIPPET_CHARS = 360


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _compact_snippet(content: str, limit: int) -> str:
    snippet = re.sub(r"\s+", " ", content).strip()
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit].rstrip() + "..."


@tool
def web_search(query: str) -> str:
    """Search the web with the Tavily API and return compact results.

    Args:
        query: Search query to send to Tavily.

    Returns:
        A numbered list containing compact results. Each result includes title,
        URL, and a bounded snippet. If Tavily is not configured or the request
        fails, returns an error message string instead of raising.
    """
    if not query.strip():
        return "Error: query cannot be empty."

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY environment variable is not set."

    max_results = _env_int("TAVILY_MAX_RESULTS", DEFAULT_TAVILY_MAX_RESULTS, 1, 5)
    snippet_chars = _env_int("TAVILY_SNIPPET_CHARS", DEFAULT_TAVILY_SNIPPET_CHARS, 80, 1200)

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])[:max_results]
    except Exception as exc:
        return f"Error: Tavily search failed: {exc}"

    if not results:
        return "No results found."

    formatted: list[str] = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or "No URL"
        content = _compact_snippet(item.get("content") or "No snippet", snippet_chars)
        formatted.append(f"{index}. {title}\nURL: {url}\nSnippet: {content}")
    return "\n\n".join(formatted)


@tool
def python_executor(code: str) -> str:
    """Execute Python code with restricted globals and captured stdout.

    Args:
        code: Python source code to execute with exec().

    Returns:
        Captured stdout with surrounding whitespace stripped. The execution
        environment exposes only math, json, re, and print; imports and regular
        builtins are unavailable. Runtime errors are returned as strings.
    """
    restricted_globals: dict[str, Any] = {
        "__builtins__": {"print": print},
        "math": math,
        "json": json,
        "re": re,
    }
    stdout = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, restricted_globals, {})
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

    output = stdout.getvalue().strip()
    return output if output else "No output."


_MATH_NAMES = {
    name: value
    for name, value in vars(math).items()
    if not name.startswith("_")
}
_CALCULATOR_GLOBALS = {"__builtins__": {}, "math": math, **_MATH_NAMES}
_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.Attribute,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Tuple,
    ast.List,
)


class _CalculatorValidator(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(f"unsupported syntax: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__") or node.id not in _CALCULATOR_GLOBALS:
            raise ValueError(f"name is not allowed: {node.id}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            not isinstance(node.value, ast.Name)
            or node.value.id != "math"
            or node.attr.startswith("_")
            or not hasattr(math, node.attr)
        ):
            raise ValueError("only public attributes on math are allowed")

    def visit_Call(self, node: ast.Call) -> None:
        self.visit(node.func)
        for arg in node.args:
            self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword.value)


@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression with eval() and no builtin access.

    Args:
        expression: Arithmetic expression using Python operators and the math
        module, for example "math.sqrt(81) + 3".

    Returns:
        The evaluated result as a string. Builtins, private attributes, imports,
        comprehensions, and unsupported syntax return an error message.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        _CalculatorValidator().visit(tree)
        result = eval(compile(tree, "<calculator>", "eval"), _CALCULATOR_GLOBALS, {})
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
    return str(result)
