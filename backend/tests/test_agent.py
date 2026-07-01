import asyncio
import unittest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage


def make_tool_call(name, call_id="call-1", **args):
    """Build an assistant AIMessage carrying a single native tool call."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages, tools=None):
        response = next(self._responses)
        return response if isinstance(response, AIMessage) else AIMessage(content=response)


class CapturingLLM(ScriptedLLM):
    def __init__(self, responses):
        super().__init__(responses)
        self.messages = []

    def invoke(self, messages, tools=None):
        self.messages.append(messages)
        return super().invoke(messages, tools)


class ToolTests(unittest.TestCase):
    def test_calculator_evaluates_math_expression(self):
        from agent.tools import calculator

        result = calculator.invoke({"expression": "math.sqrt(81) + 3"})

        self.assertEqual(result, "12.0")

    def test_calculator_rejects_builtin_access(self):
        from agent.tools import calculator

        result = calculator.invoke(
            {"expression": "__import__('os').system('echo nope')"}
        )

        self.assertIn("Error:", result)

    def test_python_executor_captures_stdout(self):
        from agent.tools import python_executor

        result = python_executor.invoke({"code": "print(math.factorial(5))"})

        self.assertEqual(result, "120")

    def test_python_executor_solves_symbolic_equation_with_sympy(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {"code": "x, y = symbols('x y'); print(solve(2*x + 4*y + 6, x))"}
        )

        self.assertIn("-2*y - 3", result)

    def test_python_executor_strips_fences_and_redundant_sympy_import(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {
                "code": """```python
from sympy import symbols, Eq, solve
x, y = symbols('x y')
eq1 = Eq(4*x + 5*y + 6, 0)
eq2 = Eq(3*x + y + 2, 0)
print(solve((eq1, eq2), (x, y)))
```"""
            }
        )

        self.assertIn("x: -4/11", result)
        self.assertIn("y: -10/11", result)

    def test_python_executor_repairs_flattened_fenced_sympy_code(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {
                "code": (
                    "``` from sympy import symbols, Eq, solve "
                    "# Declare the symbols x, y = symbols('x y') "
                    "# Define the equations eq1 = Eq(4*x + 5*y, -6) "
                    "eq2 = Eq(3*x + y, -2) "
                    "# Solve the system of equations solution = solve((eq1, eq2), (x, y)) "
                    "print(solution) ```"
                )
            }
        )

        self.assertIn("x: -4/11", result)
        self.assertIn("y: -10/11", result)

    def test_python_executor_strips_fences_and_redundant_numpy_import(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {
                "code": """```
import numpy as np
A = np.array([[4, 5], [3, 1]])
b = np.array([-6, -2])
x, y = np.linalg.solve(A, b)
print(f"x = {round(float(x), 6)}, y = {round(float(y), 6)}")
```"""
            }
        )

        self.assertIn("x = -0.363636", result)
        self.assertIn("y = -0.909091", result)

    def test_python_executor_repairs_flattened_fenced_numpy_code(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {
                "code": (
                    "``` import numpy as np "
                    "# Coefficients of the equations A = np.array([[4, 5], [3, 1]]) "
                    "b = np.array([-6, -2]) "
                    "# Solve the system of equations x, y = np.linalg.solve(A, b) "
                    'print(f"x = {round(float(x), 6)}, y = {round(float(y), 6)}") ```'
                )
            }
        )

        self.assertIn("x = -0.363636", result)
        self.assertIn("y = -0.909091", result)

    def test_python_executor_allows_safe_builtins_and_blocks_imports(self):
        from agent.tools import python_executor

        self.assertEqual(
            python_executor.invoke({"code": "print(sum(range(10)))"}), "45"
        )
        self.assertEqual(python_executor.invoke({"code": "print(len([1,2,3]))"}), "3")
        self.assertTrue(
            python_executor.invoke({"code": "import os"}).startswith("Error:")
        )

    def test_python_executor_extracts_inline_fenced_code_and_allows_sys_version(self):
        from agent.tools import python_executor

        result = python_executor.invoke(
            {
                "code": (
                    "```python import sys print(sys.version) ``` "
                    "Please run this script locally."
                )
            }
        )

        self.assertNotIn("Error:", result)
        self.assertRegex(result, r"\d+\.\d+\.\d+")

    def test_web_search_compacts_retrieved_context(self):
        from agent.tools import web_search

        long_snippet = "A" * 140
        with patch.dict(
            os.environ,
            {
                "TAVILY_API_KEY": "test-key",
                "TAVILY_MAX_RESULTS": "2",
                "TAVILY_SNIPPET_CHARS": "80",
            },
            clear=True,
        ):
            with patch("agent.tools.TavilyClient") as client_class:
                client_class.return_value.search.return_value = {
                    "results": [
                        {
                            "title": "One",
                            "url": "https://one.test",
                            "content": long_snippet,
                        },
                        {"title": "Two", "url": "https://two.test", "content": "short"},
                        {
                            "title": "Three",
                            "url": "https://three.test",
                            "content": "extra",
                        },
                    ]
                }

                result = web_search.invoke({"query": "ai agents"})

        client_class.return_value.search.assert_called_once_with(
            query="ai agents", max_results=2
        )
        self.assertIn("1. One", result)
        self.assertIn("2. Two", result)
        self.assertNotIn("3. Three", result)
        self.assertIn(f"Snippet: {'A' * 80}...", result)
        self.assertNotIn("A" * 90, result)


class GraphTests(unittest.TestCase):
    def test_web_search_gate_can_be_disabled_for_tests(self):
        from agent.graph import _requires_web_search

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": "1"}):
            self.assertFalse(
                _requires_web_search("what is the latest version of python")
            )

    def test_web_search_gate_ignores_year_numbers_in_math(self):
        from agent.graph import _requires_web_search

        # A bare year inside a math operand must not force a web search.
        self.assertFalse(_requires_web_search("What is the square root of 2025?"))
        # Temporal phrasing about a year still does.
        self.assertTrue(_requires_web_search("What major AI releases happened in 2026?"))

    def test_graph_runs_tool_then_returns_final_answer(self):
        from agent.graph import build_graph

        llm = ScriptedLLM(
            [
                make_tool_call("calculator", expression="40 + 2"),
                "42",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = asyncio.run(graph.ainvoke(
            {
                "messages": [HumanMessage(content="What is 40 + 2?")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        ))

        self.assertEqual(final_state["final_answer"], "42")
        self.assertEqual(final_state["iteration_count"], 1)
        self.assertEqual(final_state["intermediate_steps"][0]["action"], "calculator")
        self.assertEqual(final_state["intermediate_steps"][0]["observation"], "42")

    def test_graph_normalizes_fenced_python_executor_input_in_trace(self):
        from agent.graph import build_graph

        fenced = (
            "```python\n"
            "from sympy import symbols, Eq, solve\n"
            "x, y = symbols('x y')\n"
            "print(solve((Eq(4*x + 5*y + 6, 0), Eq(3*x + y + 2, 0)), (x, y)))\n"
            "```"
        )
        llm = ScriptedLLM(
            [
                make_tool_call("python_executor", code=fenced),
                "x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = asyncio.run(graph.ainvoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        ))

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("from sympy import", action_input)
        self.assertIn("x: -4/11", observation)
        self.assertIn("y: -10/11", observation)

    def test_graph_normalizes_fenced_numpy_executor_input_in_trace(self):
        from agent.graph import build_graph

        fenced = (
            "```\n"
            "import numpy as np\n"
            "A = np.array([[4, 5], [3, 1]])\n"
            "b = np.array([-6, -2])\n"
            "x, y = np.linalg.solve(A, b)\n"
            'print(f"x = {round(float(x), 6)}, y = {round(float(y), 6)}")\n'
            "```"
        )
        llm = ScriptedLLM(
            [
                make_tool_call("python_executor", code=fenced),
                "x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = asyncio.run(graph.ainvoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        ))

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("import numpy", action_input)
        self.assertIn("x = -0.363636", observation)
        self.assertIn("y = -0.909091", observation)

    def test_graph_normalizes_flattened_fenced_python_executor_input_in_trace(self):
        from agent.graph import build_graph

        flattened = (
            "``` from sympy import symbols, Eq, solve "
            "# Declare the symbols x, y = symbols('x y') "
            "# Define the equations eq1 = Eq(4*x + 5*y, -6) "
            "eq2 = Eq(3*x + y, -2) "
            "# Solve the system of equations solution = solve((eq1, eq2), (x, y)) "
            "print(solution) ```"
        )
        llm = ScriptedLLM(
            [
                make_tool_call("python_executor", code=flattened),
                "x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = asyncio.run(graph.ainvoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        ))

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("from sympy import", action_input)
        self.assertIn("x: -4/11", observation)
        self.assertIn("y: -10/11", observation)

    def test_graph_system_prompt_includes_current_date_context(self):
        from agent.graph import build_graph

        llm = CapturingLLM(["ok"])
        graph = build_graph(llm=llm)

        graph.invoke(
            {
                "messages": [HumanMessage(content="hello")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        )

        system_prompt = llm.messages[0][0].content
        self.assertIn("Current date:", system_prompt)
        self.assertIn("Dates before the current date are past dates", system_prompt)
        self.assertIn("do not repeat web_search", system_prompt)
        self.assertIn("conversational ReAct agent", system_prompt)
        self.assertIn("native tool calling", system_prompt)
        self.assertIn("run the code locally", system_prompt)
        # The text ReAct protocol is gone; tools are passed via the API now.
        self.assertNotIn("Thought:", system_prompt)

    def test_graph_forces_web_search_for_latest_version_final_answer_skip(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def __init__(self):
                self.calls = []

            def invoke(self, payload):
                self.calls.append(payload)
                return "Python 3.13.7 is the latest stable Python release."

        fake_web_search = FakeWebSearch()
        llm = ScriptedLLM(["Python 3.12.3", "Python 3.13.7"])
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = asyncio.run(graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content="what is the latest version of python")
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                ))

        self.assertEqual(
            fake_web_search.calls,
            [{"query": "what is the latest version of python"}],
        )
        self.assertEqual(final_state["final_answer"], "Python 3.13.7")
        self.assertEqual(final_state["iteration_count"], 1)
        self.assertEqual(final_state["intermediate_steps"][0]["action"], "web_search")
        self.assertEqual(
            final_state["intermediate_steps"][0]["action_input"],
            "what is the latest version of python",
        )

    def test_graph_appends_source_urls_after_web_search_when_llm_omits_them(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def invoke(self, payload):
                return (
                    "1. Python Downloads\n"
                    "URL: https://www.python.org/downloads/\n"
                    "Snippet: Download Python 3.14.4."
                )

        llm = ScriptedLLM(
            [
                make_tool_call("web_search", query="latest stable Python version"),
                "The latest stable Python version is Python 3.14.4.",
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": FakeWebSearch()}):
                final_state = asyncio.run(graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content="what is the latest version of python")
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                ))

        self.assertIn("Python 3.14.4", final_state["final_answer"])
        self.assertIn("Sources:", final_state["final_answer"])
        self.assertIn(
            "https://www.python.org/downloads/",
            final_state["final_answer"],
        )

    def test_graph_forces_web_search_for_explicit_search_request(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def __init__(self):
                self.calls = []

            def invoke(self, payload):
                self.calls.append(payload)
                return "LangGraph documentation result with source URL."

        fake_web_search = FakeWebSearch()
        llm = ScriptedLLM(
            [
                "LangGraph is a graph framework.",
                "LangGraph source-backed summary.",
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = asyncio.run(graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(
                                content="Search for LangGraph and summarize what it is"
                            )
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                ))

        self.assertEqual(
            fake_web_search.calls,
            [{"query": "Search for LangGraph and summarize what it is"}],
        )
        self.assertEqual(final_state["final_answer"], "LangGraph source-backed summary.")
        self.assertEqual(final_state["intermediate_steps"][0]["action"], "web_search")

    def test_graph_uses_previous_subject_for_source_followup(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def __init__(self):
                self.calls = []

            def invoke(self, payload):
                self.calls.append(payload)
                return "LangGraph source list with URLs."

        fake_web_search = FakeWebSearch()
        llm = ScriptedLLM(
            [
                "I did not use external sources.",
                "Sources listed.",
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = asyncio.run(graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(
                                content="Search for LangGraph and summarize what it is"
                            ),
                            AIMessage(content="LangGraph is a framework for graphs."),
                            HumanMessage(
                                content="List the sources used and what each one contributed"
                            ),
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                ))

        self.assertEqual(
            fake_web_search.calls,
            [{"query": "Search for LangGraph and summarize what it is sources"}],
        )
        self.assertEqual(final_state["final_answer"], "Sources listed.")
        self.assertEqual(
            final_state["intermediate_steps"][0]["action_input"],
            "Search for LangGraph and summarize what it is sources",
        )

    def test_graph_forces_final_after_repeated_current_fact_web_searches(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def __init__(self):
                self.calls = []

            def invoke(self, payload):
                self.calls.append(payload)
                return "Official Python downloads page says Download Python 3.14.4."

        fake_web_search = FakeWebSearch()
        llm = ScriptedLLM(
            [
                make_tool_call("web_search", call_id="ws1", query="latest Python version"),
                make_tool_call("web_search", call_id="ws2", query="latest stable Python release"),
                make_tool_call("web_search", call_id="ws3", query="current Python download"),
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = asyncio.run(graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content="what is the latest version of python")
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                ))

        self.assertEqual(len(fake_web_search.calls), 2)
        self.assertEqual(final_state["iteration_count"], 2)
        self.assertEqual(
            [step["action"] for step in final_state["intermediate_steps"]],
            ["web_search", "web_search"],
        )
        self.assertIn("Download Python 3.14.4", final_state["final_answer"])
        self.assertIn(
            "Based on the latest web_search results",
            final_state["messages"][-1].content,
        )


class MemoryToolStepTests(unittest.TestCase):
    """Verify memory_read/memory_write tool calls produce correctly-shaped Steps."""

    def _run(self, coro):
        return asyncio.run(coro)

    def _make_state(self, tool_msg):
        return {
            "messages": [tool_msg],
            "intermediate_steps": [],
            "iteration_count": 0,
            "final_answer": None,
        }

    def test_memory_read_step_has_required_keys(self):
        from agent.graph import MEMORY_READ_TOOL_NAME, tool_node

        store = MagicMock()
        store.asearch = AsyncMock(return_value=[])
        config = {"configurable": {"thread_id": "test-session"}}
        state = self._make_state(make_tool_call(MEMORY_READ_TOOL_NAME, query="recall preferences"))

        result = self._run(tool_node(state, store, config))

        self.assertEqual(len(result["intermediate_steps"]), 1)
        step = result["intermediate_steps"][-1]
        self.assertEqual(set(step.keys()), {"thought", "action", "action_input", "observation", "timestamp"})
        self.assertEqual(step["action"], MEMORY_READ_TOOL_NAME)
        self.assertEqual(step["action_input"], "recall preferences")

    def test_memory_write_step_has_required_keys(self):
        from agent.graph import MEMORY_WRITE_TOOL_NAME, tool_node

        store = MagicMock()
        store.asearch = AsyncMock(return_value=[])
        store.aput = AsyncMock(return_value=None)
        config = {"configurable": {"thread_id": "test-session"}}
        state = self._make_state(make_tool_call(MEMORY_WRITE_TOOL_NAME, content="I live in Sao Paulo"))

        result = self._run(tool_node(state, store, config))

        self.assertEqual(len(result["intermediate_steps"]), 1)
        step = result["intermediate_steps"][-1]
        self.assertEqual(set(step.keys()), {"thought", "action", "action_input", "observation", "timestamp"})
        self.assertEqual(step["action"], MEMORY_WRITE_TOOL_NAME)
        self.assertEqual(step["action_input"], "I live in Sao Paulo")

    def test_memory_read_with_none_store_returns_graceful_observation(self):
        from agent.graph import MEMORY_READ_TOOL_NAME, tool_node

        config = {"configurable": {"thread_id": "test-session"}}
        state = self._make_state(make_tool_call(MEMORY_READ_TOOL_NAME, query="anything"))

        result = self._run(tool_node(state, None, config))

        step = result["intermediate_steps"][-1]
        self.assertIn("unavailable", step["observation"].lower())

    def test_memory_write_with_none_store_returns_graceful_observation(self):
        from agent.graph import MEMORY_WRITE_TOOL_NAME, tool_node

        config = {"configurable": {"thread_id": "test-session"}}
        state = self._make_state(make_tool_call(MEMORY_WRITE_TOOL_NAME, content="some fact"))

        result = self._run(tool_node(state, None, config))

        step = result["intermediate_steps"][-1]
        self.assertIn("unavailable", step["observation"].lower())


if __name__ == "__main__":
    unittest.main()
