import ast
import importlib.util
import math
import os
import re
import subprocess
import sys
import tempfile

from langchain_core.tools import tool
from tavily import TavilyClient

_SYMPY_AVAILABLE = importlib.util.find_spec("sympy") is not None
_NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None

DEFAULT_TAVILY_MAX_RESULTS = 2
DEFAULT_TAVILY_SNIPPET_CHARS = 360

_SAFE_IMPORT_STATEMENTS = (
    r"from\s+sympy\s+import\s+(?:symbols|Eq|solve|simplify|expand|factor|Rational)"
    r"(?:\s*,\s*(?:symbols|Eq|solve|simplify|expand|factor|Rational))*",
    r"import\s+sympy(?:\s+as\s+\w+)?",
    r"import\s+numpy\s+as\s+np",
    r"import\s+numpy",
)
_FLATTENED_STATEMENT_STARTERS = (
    r"x\s*,\s*y\s*=",
    r"eq\d+\s*=",
    r"solution\s*=",
    r"print\s*\(",
    r"A\s*=",
    r"b\s*=",
)
_PYTHON_EXECUTOR_ALLOWED_IMPORTS = {
    "math",
    "json",
    "re",
    "statistics",
    "random",
    "itertools",
    "functools",
    "sympy",
    "numpy",
}
_PYTHON_EXECUTOR_BLOCKED_NAMES = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "builtins",
    "sys",
}
_PYTHON_EXECUTOR_BLOCKED_ATTRIBUTES = {
    "CDLL",
    "LibraryLoader",
    "LoadLibrary",
    "OleDLL",
    "PyDLL",
    "WinDLL",
    "ctypes",
    "ctypeslib",
}
_PYTHON_EXECUTOR_STATUS_PATTERN = re.compile(
    r"\s*\[(?:Aguardando a resposta do python_executor|Waiting for python_executor response)\.\.\.\]\s*$",
    flags=re.IGNORECASE,
)


def normalize_python_code_input(code: str) -> str:
    """Remove common Markdown wrapping and redundant safe imports."""
    stripped = code.strip()
    stripped = _strip_executor_status_annotations(stripped)
    fence_match = re.fullmatch(
        r"```\s*(?:python|py)?\s*(.*?)\s*```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fence_match:
        stripped = fence_match.group(1).strip()

    if "\n" not in stripped:
        stripped = _normalize_flattened_python_code(stripped)

    lines: list[str] = []
    for line in stripped.splitlines():
        normalized = line.strip()
        if _should_strip_safe_import_statement(normalized):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _strip_executor_status_annotations(code: str) -> str:
    return "\n".join(
        _PYTHON_EXECUTOR_STATUS_PATTERN.sub("", line) for line in code.splitlines()
    ).strip()


def _safe_import_statement_available(statement: str) -> bool:
    if "sympy" in statement:
        return _SYMPY_AVAILABLE
    if "numpy" in statement:
        return _NUMPY_AVAILABLE
    return True


def _should_strip_safe_import_statement(line: str) -> bool:
    return any(
        _safe_import_statement_available(statement)
        and re.fullmatch(rf"{statement}(?:\s*#.*)?", line)
        for statement in _SAFE_IMPORT_STATEMENTS
    )


def _normalize_flattened_python_code(code: str) -> str:
    for statement in _SAFE_IMPORT_STATEMENTS:
        if not _safe_import_statement_available(statement):
            continue
        code = re.sub(rf"\b{statement}\b", "", code, flags=re.IGNORECASE)

    starters = "|".join(_FLATTENED_STATEMENT_STARTERS)
    code = re.sub(rf"#.*?(?=(?:{starters}))", "\n", code)
    code = re.sub(rf"\s+(?=(?:{starters}))", "\n", code)
    code = re.sub(r";\s*", "\n", code)
    return code.strip()


class _PythonExecutorValidator(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_level_module = alias.name.split(".")[0]
            if top_level_module not in _PYTHON_EXECUTOR_ALLOWED_IMPORTS:
                raise ValueError(
                    f"ImportError: import '{alias.name}' is not allowed in this sandbox"
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        top_level_module = (node.module or "").split(".")[0]
        if node.level or top_level_module not in _PYTHON_EXECUTOR_ALLOWED_IMPORTS:
            module_name = "." * node.level + (node.module or "")
            raise ValueError(
                f"ImportError: import '{module_name}' is not allowed in this sandbox"
            )

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("_") or node.id in _PYTHON_EXECUTOR_BLOCKED_NAMES:
            raise ValueError(f"name '{node.id}' is not allowed in this sandbox")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            node.attr.startswith("_")
            or node.attr in _PYTHON_EXECUTOR_BLOCKED_ATTRIBUTES
        ):
            raise ValueError(f"attribute '{node.attr}' is not allowed in this sandbox")
        self.generic_visit(node)


def _validate_python_executor_code(code: str) -> str | None:
    try:
        tree = ast.parse(code, filename="<python_executor>", mode="exec")
    except SyntaxError as exc:
        return f"Error: SyntaxError: {exc.msg}"

    try:
        _PythonExecutorValidator().visit(tree)
    except ValueError as exc:
        return f"Error: {exc}"

    return None


def _sanitize_python_executor_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "Unknown subprocess error."


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
    snippet_chars = _env_int(
        "TAVILY_SNIPPET_CHARS", DEFAULT_TAVILY_SNIPPET_CHARS, 80, 1200
    )

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

    Sympy is available when installed. To solve 2x + 4y + 6 = 0 for x:
    x, y = symbols('x y')
    print(solve(2*x + 4*y + 6, x))

    Args:
        code: Python source code to execute with exec().

    Returns:
        Captured stdout with surrounding whitespace stripped. The execution
        environment exposes a safe whitelist of common builtins, plus math,
        json, re, statistics, random, itertools, functools, numpy as np when
        installed, and sympy helpers when installed. Markdown code fences and
        redundant safe imports for sympy/numpy are stripped before execution.
        Other imports and unsafe builtins such as open, eval, exec, compile,
        globals, locals, vars, getattr, setattr, and __import__ are unavailable.
        Runtime errors are returned as strings.
    """
    code = normalize_python_code_input(code)
    if not _SYMPY_AVAILABLE and re.search(
        r"(?<!\.)\b(?:symbols|Eq|solve|simplify|expand|factor|Rational)\b",
        code,
    ):
        return "Error: sympy is not installed in this environment. Symbolic algebra is unavailable."
    if not _NUMPY_AVAILABLE and re.search(r"(?:\bnp\s*\.|\bnumpy\b)", code):
        return "Error: numpy is not installed in this environment."

    validation_error = _validate_python_executor_code(code)
    if validation_error is not None:
        return validation_error

    safe_wrapper = """
import sys, builtins

import functools, itertools, json, math, random, re, statistics
try:
    import sympy
    from sympy import Eq, Rational, expand, factor, simplify, solve, symbols
    _x, _y = symbols("_x _y")
    solve(2 * _x + 4 * _y + 6, _x)
except ImportError:
    pass
try:
    import numpy as np
    numpy = np
except ImportError:
    pass

def _format_exception(exc_type, exc, tb):
    sys.stderr.write(f"{exc_type.__name__}: {exc}")

sys.excepthook = _format_exception

_BLOCKED = {
    "open", "exec", "eval", "compile", "__import__",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
}
_ALLOWED_MODULES = {
    "math", "json", "re", "statistics", "random",
    "itertools", "functools", "sympy", "numpy",
}

_real_import = builtins.__import__
_real_exec = builtins.exec

def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    level = kwargs.get("level", args[3] if len(args) > 3 else 0)
    package = ""
    if args and isinstance(args[0], dict):
        package = args[0].get("__package__", "") or ""
    if package.split(".")[0] in _ALLOWED_MODULES:
        return _real_import(name, *args, **kwargs)
    if top not in _ALLOWED_MODULES:
        raise ImportError(f"import '{name}' is not allowed in this sandbox")
    return _real_import(name, *args, **kwargs)

def _safe_exec(source, globals=None, locals=None):
    try:
        package = sys._getframe(1).f_globals.get("__package__", "") or ""
    except Exception:
        package = ""
    if package.split(".")[0] not in _ALLOWED_MODULES:
        raise RuntimeError("exec is not allowed in this sandbox")
    if globals is None:
        return _real_exec(source)
    if locals is None:
        return _real_exec(source, globals)
    return _real_exec(source, globals, locals)

builtins.__import__ = _safe_import
_compile = builtins.compile
_exec = _real_exec
_delattr = builtins.delattr
_hasattr = builtins.hasattr
for name in list(_BLOCKED):
    if name in {"__import__", "getattr", "locals", "setattr"}:
        continue
    if _hasattr(builtins, name):
        try:
            _delattr(builtins, name)
        except AttributeError:
            pass
builtins.exec = _safe_exec
del builtins
""".strip()
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(
                f"{safe_wrapper}\n"
                f"_USER_CODE = {code!r}\n"
                "_exec(_compile(_USER_CODE, '<python_executor>', 'exec'))"
            )

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONPATH": ""},
        )
    except subprocess.TimeoutExpired:
        return "Error: execution timed out (10s limit)."
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if result.returncode != 0:
        return f"Error: {_sanitize_python_executor_error(result.stderr)}"

    output = result.stdout.strip()
    return output if output else "No output."


_MATH_NAMES = {
    name: value for name, value in vars(math).items() if not name.startswith("_")
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
