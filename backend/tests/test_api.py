import unittest

from fastapi.testclient import TestClient


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


class ApiTests(unittest.TestCase):
    def setUp(self):
        import api

        self.api = api
        self.original_build_graph = api.build_graph
        api.build_graph = lambda: FakeGraph()
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

    def test_agent_invoke_matches_public_portfolio_endpoint_contract(self):
        response = self.client.post("/agent/invoke", json={"query": "use the fake graph"})

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
        self.api.build_graph = lambda: self.fail("simple math should not call the LLM graph")

        response = self.client.post("/run", json={"query": "What is 40 + 2?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "42")
        self.assertEqual(body["tools_used"], ["calculator"])
        self.assertEqual(body["steps"][0]["action"], "calculator")
        self.assertEqual(body["steps"][0]["observation"], "42")

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
