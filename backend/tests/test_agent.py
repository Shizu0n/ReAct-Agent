import unittest
import os
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages):
        return AIMessage(content=next(self._responses))


class CapturingLLM(ScriptedLLM):
    def __init__(self, responses):
        super().__init__(responses)
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return super().invoke(messages)


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


class ShortcutTests(unittest.TestCase):
    def test_simple_arithmetic_uses_calculator_shortcut(self):
        from agent.shortcuts import try_shortcut

        shortcut = try_shortcut("What is 40 + 2?")

        self.assertIsNotNone(shortcut)
        self.assertEqual(shortcut.final_answer, "42")
        self.assertEqual(shortcut.step["action"], "calculator")

    def test_current_search_queries_do_not_use_shortcut(self):
        from agent.shortcuts import try_shortcut

        shortcut = try_shortcut("Search the latest AI agent trends and summarize them.")

        self.assertIsNone(shortcut)

    def test_compound_growth_uses_calculator_shortcut(self):
        from agent.shortcuts import try_shortcut

        shortcut = try_shortcut(
            "Calculate the compound growth of $10,000 at 8% for 5 years."
        )

        self.assertIsNotNone(shortcut)
        self.assertEqual(shortcut.step["action"], "calculator")
        self.assertEqual(
            shortcut.final_answer,
            "The investment grows to about $14,693.28 after 5 years.",
        )

    def test_basic_statistics_uses_python_shortcut(self):
        from agent.shortcuts import try_shortcut

        shortcut = try_shortcut(
            "Use Python to calculate the mean, median, and standard deviation of [12, 18, 21, 25, 31]."
        )

        self.assertIsNotNone(shortcut)
        self.assertEqual(shortcut.step["action"], "python_executor")
        self.assertIn("mean: 21.4", shortcut.final_answer)
        self.assertIn("median: 21", shortcut.final_answer)
        self.assertIn("sample standard deviation", shortcut.final_answer)

    def test_square_root_shortcut_explains_steps(self):
        from agent.shortcuts import try_shortcut

        shortcut = try_shortcut("Calculate √1764 and explain the steps")

        self.assertIsNotNone(shortcut)
        self.assertEqual(shortcut.step["action"], "calculator")
        self.assertEqual(shortcut.step["action_input"], "math.sqrt(1764)")
        self.assertIn("√1764 = 42", shortcut.final_answer)
        self.assertIn("42 × 42 = 1764", shortcut.final_answer)

    def test_contextual_followup_explains_previous_square_root(self):
        from agent.shortcuts import try_contextual_shortcut

        shortcut = try_contextual_shortcut(
            "explain more the steps",
            ["Calculate √1764 and explain the steps", "√1764 = 42."],
        )

        self.assertIsNotNone(shortcut)
        self.assertEqual(shortcut.step["action"], "calculator")
        self.assertIn("42 × 42 = 1764", shortcut.final_answer)


class GraphTests(unittest.TestCase):
    def test_web_search_gate_can_be_disabled_for_tests(self):
        from agent.graph import _requires_web_search

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": "1"}):
            self.assertFalse(
                _requires_web_search("what is the latest version of python")
            )

    def test_graph_runs_tool_then_returns_final_answer(self):
        from agent.graph import build_graph

        llm = ScriptedLLM(
            [
                "Thought: Need arithmetic.\nAction: calculator\nAction Input: 40 + 2",
                "Thought: I have the answer.\nFinal Answer: 42",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = graph.invoke(
            {
                "messages": [HumanMessage(content="What is 40 + 2?")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        )

        self.assertEqual(final_state["final_answer"], "42")
        self.assertEqual(final_state["iteration_count"], 1)
        self.assertEqual(final_state["intermediate_steps"][0]["action"], "calculator")
        self.assertEqual(final_state["intermediate_steps"][0]["observation"], "42")

    def test_graph_normalizes_fenced_python_executor_input_in_trace(self):
        from agent.graph import build_graph

        llm = ScriptedLLM(
            [
                "Thought: Need sympy.\n"
                "Action: python_executor\n"
                "Action Input: ```python\n"
                "from sympy import symbols, Eq, solve\n"
                "x, y = symbols('x y')\n"
                "print(solve((Eq(4*x + 5*y + 6, 0), Eq(3*x + y + 2, 0)), (x, y)))\n"
                "```",
                "Thought: I have the answer.\nFinal Answer: x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = graph.invoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        )

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("from sympy import", action_input)
        self.assertIn("x: -4/11", observation)
        self.assertIn("y: -10/11", observation)

    def test_graph_normalizes_fenced_numpy_executor_input_in_trace(self):
        from agent.graph import build_graph

        llm = ScriptedLLM(
            [
                "Thought: Need numeric solve.\n"
                "Action: python_executor\n"
                "Action Input: ```\n"
                "import numpy as np\n"
                "A = np.array([[4, 5], [3, 1]])\n"
                "b = np.array([-6, -2])\n"
                "x, y = np.linalg.solve(A, b)\n"
                'print(f"x = {round(float(x), 6)}, y = {round(float(y), 6)}")\n'
                "```",
                "Thought: I have the answer.\nFinal Answer: x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = graph.invoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        )

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("import numpy", action_input)
        self.assertIn("x = -0.363636", observation)
        self.assertIn("y = -0.909091", observation)

    def test_graph_normalizes_flattened_fenced_python_executor_input_in_trace(self):
        from agent.graph import build_graph

        llm = ScriptedLLM(
            [
                "Thought: Need sympy.\n"
                "Action: python_executor\n"
                "Action Input: ``` from sympy import symbols, Eq, solve "
                "# Declare the symbols x, y = symbols('x y') "
                "# Define the equations eq1 = Eq(4*x + 5*y, -6) "
                "eq2 = Eq(3*x + y, -2) "
                "# Solve the system of equations solution = solve((eq1, eq2), (x, y)) "
                "print(solution) ```",
                "Thought: I have the answer.\nFinal Answer: x = -4/11, y = -10/11",
            ]
        )
        graph = build_graph(llm=llm)

        final_state = graph.invoke(
            {
                "messages": [HumanMessage(content="Solve the system")],
                "intermediate_steps": [],
                "iteration_count": 0,
                "final_answer": None,
            }
        )

        action_input = final_state["intermediate_steps"][0]["action_input"]
        observation = final_state["intermediate_steps"][0]["observation"]
        self.assertNotIn("```", action_input)
        self.assertNotIn("from sympy import", action_input)
        self.assertIn("x: -4/11", observation)
        self.assertIn("y: -10/11", observation)

    def test_graph_system_prompt_includes_current_date_context(self):
        from agent.graph import build_graph

        llm = CapturingLLM(["Thought: Done.\nFinal Answer: ok"])
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

    def test_graph_forces_web_search_for_latest_version_final_answer_skip(self):
        from agent.graph import TOOLS, build_graph

        class FakeWebSearch:
            def __init__(self):
                self.calls = []

            def invoke(self, payload):
                self.calls.append(payload)
                return "Python 3.13.7 is the latest stable Python release."

        fake_web_search = FakeWebSearch()
        llm = ScriptedLLM(
            [
                "Thought: I know this from memory.\nFinal Answer: Python 3.12.3",
                "Thought: The search result says Python 3.13.7.\nFinal Answer: Python 3.13.7",
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = graph.invoke(
                    {
                        "messages": [
                            HumanMessage(content="what is the latest version of python")
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                )

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
                "Thought: Need current data.\nAction: web_search\nAction Input: latest Python version",
                "Thought: These dates seem future.\nAction: web_search\nAction Input: latest stable Python release",
                "Thought: Still confused by dates.\nAction: web_search\nAction Input: currently available Python download",
            ]
        )
        graph = build_graph(llm=llm)

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            with patch.dict(TOOLS, {"web_search": fake_web_search}):
                final_state = graph.invoke(
                    {
                        "messages": [
                            HumanMessage(content="what is the latest version of python")
                        ],
                        "intermediate_steps": [],
                        "iteration_count": 0,
                        "final_answer": None,
                    }
                )

        self.assertEqual(len(fake_web_search.calls), 2)
        self.assertEqual(final_state["iteration_count"], 2)
        self.assertEqual(
            [step["action"] for step in final_state["intermediate_steps"]],
            ["web_search", "web_search"],
        )
        self.assertIn("Download Python 3.14.4", final_state["final_answer"])
        self.assertIn(
            "repeating web_search would risk a loop",
            final_state["messages"][-1].content,
        )


if __name__ == "__main__":
    unittest.main()
