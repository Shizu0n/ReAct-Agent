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


class _FakeMcpTool:
    """Minimal stand-in for a discovered MCP BaseTool: a name + async ainvoke."""

    def __init__(self, name, result=None, raises=False):
        self.name = name
        self._result = result
        self._raises = raises

    async def ainvoke(self, args):
        if self._raises:
            raise RuntimeError("mcp boom")
        return self._result


def _mcp_call_message(name="fetch_url", args=None):
    return AIMessage(
        content="I should read that page",
        tool_calls=[{"name": name, "args": args or {"url": "http://example.com"}, "id": "mcp-0"}],
    )


class McpToolNodeTests(unittest.TestCase):
    """MCP-03: an MCP tool call executes in the graph and renders like a native one."""

    def test_mcp_step_shape_matches_native(self):
        from agent.graph import tool_node

        config = {"configurable": {"thread_id": "mcp-session"}}
        native = asyncio.run(
            tool_node(_state(_calculator_call_message("2 + 2")), None, config)
        )
        native_keys = set(native["intermediate_steps"][-1].keys())

        fake = _FakeMcpTool("fetch_url", result="MCP RESULT")
        result = asyncio.run(
            tool_node(
                _state(_mcp_call_message("fetch_url", {"url": "http://example.com"})),
                None,
                config,
                mcp_tools={"fetch_url": fake},
            )
        )
        step = result["intermediate_steps"][-1]
        self.assertEqual(set(step.keys()), native_keys)
        self.assertEqual(step["action"], "fetch_url")
        self.assertEqual(step["observation"], "MCP RESULT")
        self.assertIsInstance(step["elapsed_ms"], int)
        self.assertGreaterEqual(step["elapsed_ms"], 0)

    def test_mcp_content_blocks_flattened_to_text(self):
        from agent.graph import tool_node

        config = {"configurable": {"thread_id": "mcp-session"}}
        fake = _FakeMcpTool(
            "fetch_url", result=[{"type": "text", "text": "clean text", "id": "x"}]
        )
        result = asyncio.run(
            tool_node(
                _state(_mcp_call_message("fetch_url")),
                None,
                config,
                mcp_tools={"fetch_url": fake},
            )
        )
        self.assertEqual(result["intermediate_steps"][-1]["observation"], "clean text")

    def test_mcp_tool_error_becomes_observation(self):
        from agent.graph import tool_node

        config = {"configurable": {"thread_id": "mcp-session"}}
        fake = _FakeMcpTool("fetch_url", raises=True)
        result = asyncio.run(
            tool_node(
                _state(_mcp_call_message("fetch_url")),
                None,
                config,
                mcp_tools={"fetch_url": fake},
            )
        )
        self.assertTrue(result["intermediate_steps"][-1]["observation"].startswith("Error:"))

    def test_collision_with_native_tool_is_dropped(self):
        from agent.graph import _filter_mcp_tools

        tools = [_FakeMcpTool("calculator"), _FakeMcpTool("novel")]
        schemas = [{"function": {"name": "calculator"}}, {"function": {"name": "novel"}}]
        tool_map, active_schemas = _filter_mcp_tools(tools, schemas)
        self.assertNotIn("calculator", tool_map)
        self.assertIn("novel", tool_map)
        self.assertEqual(len(active_schemas), len(tool_map))
        self.assertEqual(active_schemas, [{"function": {"name": "novel"}}])


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
