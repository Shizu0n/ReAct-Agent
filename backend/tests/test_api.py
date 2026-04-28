import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


STEP = {
    "thought": "Need arithmetic.",
    "action": "calculator",
    "action_input": "40 + 2",
    "observation": "42",
    "timestamp": "2026-04-26T00:00:00+00:00",
}


class FakeGraph:
    def invoke(self, initial_state):
        return {
            **initial_state,
            "intermediate_steps": [STEP],
            "iteration_count": 1,
            "final_answer": "42",
        }

    def stream(self, initial_state, stream_mode="values"):
        yield initial_state
        yield {
            **initial_state,
            "intermediate_steps": [STEP],
            "iteration_count": 1,
            "final_answer": None,
        }
        yield {
            **initial_state,
            "intermediate_steps": [STEP],
            "iteration_count": 1,
            "final_answer": "42",
        }


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages):
        return AIMessage(content=next(self._responses))


class FakeWebSearch:
    def __init__(self):
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return "Search result: Python 3.13.7 is the latest stable Python release."


class FakeGraphWithSpy(FakeGraph):
    def __init__(self):
        self.invoked_tools = []
        self.web_search = FakeWebSearch()

    def invoke(self, initial_state):
        query = str(initial_state["messages"][-1].content)
        if self._should_run_enforcement_graph(query):
            final_state = self._run_enforcement_graph(initial_state)
        else:
            final_state = super().invoke(initial_state)

        self.invoked_tools = [
            step["action"]
            for step in final_state.get("intermediate_steps", [])
            if step.get("action")
        ]
        return final_state

    def _should_run_enforcement_graph(self, query):
        from agent.graph import _requires_web_search

        return _requires_web_search(query)

    def _run_enforcement_graph(self, initial_state):
        from agent.graph import TOOLS, build_graph

        llm = ScriptedLLM(
            [
                "Thought: I know this from memory.\nFinal Answer: Python 3.13 is currently in beta",
                "Thought: I checked the web result.\nFinal Answer: Search-backed current answer.",
            ]
        )
        graph = build_graph(llm=llm)
        with patch.dict(TOOLS, {"web_search": self.web_search}):
            return graph.invoke(initial_state)


class ApiTests(unittest.TestCase):
    def setUp(self):
        import api

        self.api = api
        self.original_build_graph = api.build_graph
        api.build_graph = lambda: FakeGraphWithSpy()
        api.RUNS.clear()
        api.RUN_ORDER.clear()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.build_graph = self.original_build_graph
        self.client.close()

    def test_health_lists_tools(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "tools": ["web_search", "python_executor", "calculator"]},
        )

    def test_config_reports_model_chain_without_secrets(self):
        with patch.dict(
            os.environ,
            {
                "REACT_AGENT_SKIP_DOTENV": "1",
                "GEMINI_API_KEY": "test-gemini-secret",
                "GROQ_API_KEY": "test-groq-secret",
            },
            clear=True,
        ):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "configured")
        self.assertEqual(body["active_model"]["provider"], "gemini")
        self.assertEqual(body["active_model"]["model"], "gemini-2.5-flash")
        self.assertEqual(body["active_model"]["label"], "Gemini 2.5 Flash")
        self.assertEqual(
            [model["provider"] for model in body["fallback_models"]], ["groq"]
        )
        self.assertNotIn("test-gemini-secret", str(body))
        self.assertNotIn("test-groq-secret", str(body))

    def test_run_returns_response_and_trace_can_be_retrieved(self):
        response = self.client.post("/run", json={"query": "use the fake graph"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "42")
        self.assertEqual(body["trace"], [STEP])
        self.assertEqual(body["answer"], "42")
        self.assertEqual(body["steps"], [STEP])
        self.assertEqual(body["tools_used"], ["calculator"])
        self.assertEqual(body["status"], "success")
        self.assertIsInstance(body["latency_ms"], int)
        self.assertIsInstance(body["total_time"], float)
        self.assertTrue(body["run_id"])

        trace_response = self.client.get(f"/trace/{body['run_id']}")
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(trace_response.json(), body)

    def test_version_query_triggers_web_search(self):
        """Regression guard for 2026-04-27: the agent answered "Python 3.13 is currently in beta" without web_search."""
        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            response = self.client.post(
                "/api/run",
                json={"query": "what is the latest version of python", "stream": False},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertIn("web_search", body["tools_used"])

    def test_stale_knowledge_query_does_not_skip_tools(self):
        """Regression guard for 2026-04-27: the agent answered "Python 3.13 is currently in beta" from stale memory."""
        queries = [
            "what is the current price of bitcoin",
            "latest news about AI",
        ]

        with patch.dict(os.environ, {"REACT_AGENT_DISABLE_WEB_SEARCH_GATE": ""}):
            for query in queries:
                with self.subTest(query=query):
                    response = self.client.post(
                        "/api/run",
                        json={"query": query, "stream": False},
                    )

                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["status"], "success")
                    self.assertTrue(body["tools_used"])
                    self.assertIn("web_search", body["tools_used"])

    def test_math_query_does_not_require_web_search(self):
        """Regression guard for 2026-04-27: preventing "Python 3.13 is currently in beta" must not overfire on math."""
        response = self.client.post(
            "/api/run",
            json={"query": "what is 2 + 2", "stream": False},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertNotIn("web_search", body["tools_used"])
        self.assertIn("calculator", body["tools_used"])

    def test_run_passes_recent_chat_history_to_graph(self):
        captured = {}

        class CapturingGraph(FakeGraph):
            def invoke(self, initial_state):
                captured["messages"] = initial_state["messages"]
                return super().invoke(initial_state)

        self.api.build_graph = lambda: CapturingGraph()

        response = self.client.post(
            "/run",
            json={
                "query": "explain more the steps",
                "history": [
                    {
                        "role": "user",
                        "content": "Compare LangGraph and plain LangChain",
                    },
                    {
                        "role": "assistant",
                        "content": "LangGraph is better for explicit state machines.",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        messages = captured["messages"]
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, "Compare LangGraph and plain LangChain")
        self.assertIsInstance(messages[1], AIMessage)
        self.assertEqual(
            messages[1].content, "LangGraph is better for explicit state machines."
        )
        self.assertIsInstance(messages[2], HumanMessage)
        self.assertEqual(messages[2].content, "explain more the steps")

    def test_contextual_math_followup_bypasses_llm_graph(self):
        self.api.build_graph = lambda: self.fail(
            "contextual math follow-up should not call the LLM graph"
        )

        response = self.client.post(
            "/run",
            json={
                "query": "explain more the steps",
                "history": [
                    {
                        "role": "user",
                        "content": "Calculate √1764 and explain the steps",
                    },
                    {"role": "assistant", "content": "√1764 = 42."},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("42 × 42 = 1764", body["result"])
        self.assertEqual(body["tools_used"], ["calculator"])

    def test_agent_invoke_matches_public_portfolio_endpoint_contract(self):
        response = self.client.post(
            "/agent/invoke", json={"query": "use the fake graph"}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "42")
        self.assertEqual(body["trace"], [STEP])
        self.assertEqual(body["answer"], "42")
        self.assertEqual(body["steps"], [STEP])
        self.assertEqual(body["tools_used"], ["calculator"])
        self.assertEqual(body["status"], "success")
        self.assertIsInstance(body["latency_ms"], int)
        self.assertIsInstance(body["total_time"], float)
        self.assertTrue(body["run_id"])

    def test_simple_math_shortcut_bypasses_llm_graph(self):
        self.api.build_graph = lambda: self.fail(
            "simple math should not call the LLM graph"
        )

        response = self.client.post("/run", json={"query": "What is 40 + 2?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "42")
        self.assertEqual(body["tools_used"], ["calculator"])
        self.assertGreaterEqual(len(body["steps"]), 2)
        self.assertEqual(body["steps"][0]["action"], "calculator")
        self.assertEqual(
            body["steps"][0]["thought"], "Use deterministic calculator; no LLM needed."
        )
        self.assertEqual(body["steps"][0]["observation"], "42")
        self.assertEqual(body["steps"][-1]["type"], "final")

    def test_stream_run_emits_step_and_final_events(self):
        with self.client.stream(
            "POST",
            "/run",
            json={"query": "use the fake graph", "stream": True},
        ) as response:
            self.assertEqual(response.status_code, 200)
            text = "\n".join(response.iter_lines())

        self.assertIn('"type": "thought"', text)
        self.assertIn('"type": "action"', text)
        self.assertIn('"type": "observation"', text)
        self.assertIn('"type": "final"', text)
        self.assertIn('"content": "42"', text)

    def test_get_stream_run_supports_eventsource_clients(self):
        with self.client.stream(
            "GET",
            "/api/run?query=use%20the%20fake%20graph&stream=true",
        ) as response:
            self.assertEqual(response.status_code, 200)
            text = "\n".join(response.iter_lines())

        self.assertIn('"type": "thought"', text)
        self.assertIn('"type": "action"', text)
        self.assertIn('"tool": "calculator"', text)
        self.assertIn('"type": "final"', text)

    def test_trace_unknown_run_returns_404(self):
        response = self.client.get("/trace/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
