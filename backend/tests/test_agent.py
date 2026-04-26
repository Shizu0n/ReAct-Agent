import unittest
import os
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages):
        return AIMessage(content=next(self._responses))


class ToolTests(unittest.TestCase):
    def test_calculator_evaluates_math_expression(self):
        from agent.tools import calculator

        result = calculator.invoke({"expression": "math.sqrt(81) + 3"})

        self.assertEqual(result, "12.0")

    def test_calculator_rejects_builtin_access(self):
        from agent.tools import calculator

        result = calculator.invoke({"expression": "__import__('os').system('echo nope')"})

        self.assertIn("Error:", result)

    def test_python_executor_captures_stdout(self):
        from agent.tools import python_executor

        result = python_executor.invoke({"code": "print(math.factorial(5))"})

        self.assertEqual(result, "120")

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
                        {"title": "One", "url": "https://one.test", "content": long_snippet},
                        {"title": "Two", "url": "https://two.test", "content": "short"},
                        {"title": "Three", "url": "https://three.test", "content": "extra"},
                    ]
                }

                result = web_search.invoke({"query": "ai agents"})

        client_class.return_value.search.assert_called_once_with(query="ai agents", max_results=2)
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

        shortcut = try_shortcut("Calculate the compound growth of $10,000 at 8% for 5 years.")

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


class GraphTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
