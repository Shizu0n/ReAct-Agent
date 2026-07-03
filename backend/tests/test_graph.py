import asyncio
import unittest

from langchain_core.messages import AIMessage


def _calculator_call_message(*expressions):
    """Build an assistant AIMessage carrying one calculator tool call per expression."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "calculator", "args": {"expression": expr}, "id": f"call-{index}"}
            for index, expr in enumerate(expressions)
        ],
    )


def _state(message):
    return {
        "messages": [message],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }


class StepTimingTests(unittest.TestCase):
    def test_step_has_integer_elapsed_ms(self):
        from agent.graph import tool_node

        config = {"configurable": {"thread_id": "timing-session"}}
        result = asyncio.run(
            tool_node(_state(_calculator_call_message("2 + 2")), None, config)
        )

        step = result["intermediate_steps"][-1]
        self.assertIn("elapsed_ms", step)
        self.assertIsInstance(step["elapsed_ms"], int)
        self.assertGreaterEqual(step["elapsed_ms"], 0)

    def test_elapsed_ms_is_per_call_not_shared(self):
        from agent.graph import tool_node

        config = {"configurable": {"thread_id": "timing-session"}}
        result = asyncio.run(
            tool_node(
                _state(_calculator_call_message("2 + 2", "3 * 3")), None, config
            )
        )

        steps = result["intermediate_steps"]
        self.assertEqual(len(steps), 2)
        for step in steps:
            self.assertIsInstance(step["elapsed_ms"], int)
            self.assertGreaterEqual(step["elapsed_ms"], 0)


if __name__ == "__main__":
    unittest.main()
