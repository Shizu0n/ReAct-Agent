import asyncio
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


def _stub_pool(fetchall_rows=None, fetchone_row=None):
    """MagicMock async pool that records execute() calls and returns canned rows."""
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=fetchall_rows or [])
    cur.fetchone = AsyncMock(return_value=fetchone_row)
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


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

    async def ainvoke(self, initial_state, config=None):
        return self.invoke(initial_state)

    async def astream(self, initial_state, config=None, stream_mode="values"):
        for state in self.stream(initial_state, stream_mode=stream_mode):
            yield state


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def invoke(self, messages, tools=None):
        response = next(self._responses)
        return response if isinstance(response, AIMessage) else AIMessage(content=response)


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

    def _should_run_enforcement_graph(self, query):
        from agent.graph import _requires_web_search

        return _requires_web_search(query)

    async def _run_enforcement_graph(self, initial_state):
        from agent.graph import TOOLS, build_graph

        llm = ScriptedLLM(
            [
                "Python 3.13 is currently in beta",
                "Search-backed current answer.",
            ]
        )
        graph = build_graph(llm=llm)
        with patch.dict(TOOLS, {"web_search": self.web_search}):
            return await graph.ainvoke(initial_state)

    async def ainvoke(self, initial_state, config=None):
        query = str(initial_state["messages"][-1].content)
        if self._should_run_enforcement_graph(query):
            final_state = await self._run_enforcement_graph(initial_state)
        else:
            final_state = super().invoke(initial_state)

        self.invoked_tools = [
            step["action"]
            for step in final_state.get("intermediate_steps", [])
            if step.get("action")
        ]
        return final_state


class _FakeKeepaliveConn:
    def __init__(self):
        self.executed = []

    async def execute(self, query, params=None):
        self.executed.append((query, params))


class _FakeKeepalivePooler:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class ApiTests(unittest.TestCase):
    def setUp(self):
        import api

        self.api = api
        self.original_build_graph = api.build_graph
        api.build_graph = lambda *a, **k: FakeGraphWithSpy()
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

    def test_keepalive_valid_token_updates(self):
        conn = _FakeKeepaliveConn()
        with patch.dict(os.environ, {"CRON_SECRET": "test-secret"}), patch(
            "agent.db.pooler_connection", lambda: _FakeKeepalivePooler(conn)
        ):
            response = self.client.get(
                "/keepalive", headers={"Authorization": "Bearer test-secret"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(len(conn.executed), 1)
        self.assertIn("UPDATE keepalive", conn.executed[0][0])

    def test_keepalive_wrong_token_returns_401_without_write(self):
        conn = _FakeKeepaliveConn()
        with patch.dict(os.environ, {"CRON_SECRET": "test-secret"}), patch(
            "agent.db.pooler_connection", lambda: _FakeKeepalivePooler(conn)
        ):
            response = self.client.get(
                "/keepalive", headers={"Authorization": "Bearer wrong"}
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(conn.executed, [])

    def test_keepalive_missing_token_returns_401(self):
        conn = _FakeKeepaliveConn()
        with patch.dict(os.environ, {"CRON_SECRET": "test-secret"}), patch(
            "agent.db.pooler_connection", lambda: _FakeKeepalivePooler(conn)
        ):
            response = self.client.get("/api/keepalive")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(conn.executed, [])

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
        # The responder prefers Gemini, so /config surfaces it as the active model.
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

        self.api.build_graph = lambda *a, **k: CapturingGraph()

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

    def test_stream_run_reports_graph_startup_errors_as_final_event(self):
        def raise_startup_error(*args, **kwargs):
            raise RuntimeError("No free model provider configured.")

        self.api.build_graph = raise_startup_error

        with self.client.stream(
            "POST",
            "/run",
            json={"query": "hello", "stream": True},
        ) as response:
            self.assertEqual(response.status_code, 200)
            text = "\n".join(response.iter_lines())

        self.assertIn('"type": "final"', text)
        self.assertIn('"status": "error"', text)
        self.assertIn("No free model provider configured", text)

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


class MemorySessionTests(unittest.TestCase):
    def setUp(self):
        import api
        self.api = api

    def test_valid_uuid_is_accepted_by_is_valid_session_id(self):
        valid = "12345678-1234-1234-1234-123456789abc"
        self.assertTrue(self.api._is_valid_session_id(valid))

    def test_empty_string_is_rejected(self):
        self.assertFalse(self.api._is_valid_session_id(""))

    def test_non_uuid_string_is_rejected(self):
        self.assertFalse(self.api._is_valid_session_id("not-a-uuid"))
        self.assertFalse(self.api._is_valid_session_id("123"))
        self.assertFalse(self.api._is_valid_session_id("12345678-1234-1234-1234-ZZZZZZZZZZZZ"))

    def test_get_session_id_returns_valid_uuid_header(self):
        from unittest.mock import MagicMock

        valid_uuid = "12345678-1234-1234-1234-123456789abc"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = valid_uuid

        result = self.api._get_session_id(mock_request)
        self.assertEqual(result, valid_uuid)

    def test_get_session_id_missing_header_returns_fresh_uuid(self):
        import re
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""

        result = self.api._get_session_id(mock_request)
        uuid_pattern = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        self.assertIsNotNone(uuid_pattern.fullmatch(result))

    def test_get_session_id_malformed_header_returns_fresh_uuid(self):
        import re
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "not-a-valid-uuid"

        result = self.api._get_session_id(mock_request)
        uuid_pattern = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        self.assertIsNotNone(uuid_pattern.fullmatch(result))

    def test_graph_config_nests_thread_id_under_configurable(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        config = self.api._graph_config(session_id)
        # Without an explicit user, the thread doubles as the user scope.
        self.assertEqual(
            config,
            {"configurable": {"thread_id": session_id, "user_id": session_id}},
        )

    def test_graph_config_carries_user_and_thread(self):
        thread_id = "11111111-1111-1111-1111-111111111111"
        user_id = "22222222-2222-2222-2222-222222222222"
        config = self.api._graph_config(thread_id, user_id)
        self.assertEqual(
            config,
            {"configurable": {"thread_id": thread_id, "user_id": user_id}},
        )

    def test_get_thread_id_header_wins(self):
        from unittest.mock import MagicMock

        thread_id = "11111111-1111-1111-1111-111111111111"
        session_id = "22222222-2222-2222-2222-222222222222"
        mock_request = MagicMock()
        mock_request.headers.get.return_value = thread_id

        self.assertEqual(self.api._get_thread_id(mock_request, session_id), thread_id)

    def test_get_thread_id_falls_back_to_session(self):
        from unittest.mock import MagicMock

        session_id = "22222222-2222-2222-2222-222222222222"
        for header in ("", "not-a-uuid"):
            mock_request = MagicMock()
            mock_request.headers.get.return_value = header
            self.assertEqual(
                self.api._get_thread_id(mock_request, session_id), session_id
            )


class ClearMemoryTests(unittest.TestCase):
    def setUp(self):
        import api
        self.api = api

        self.mock_conn = MagicMock()
        # clear_memory first SELECTs the user's thread ids from traces, then
        # DELETEs the memory store rows; the cursor's fetchall must be awaitable.
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchall = AsyncMock(return_value=[])
        self.mock_conn.execute = AsyncMock(return_value=self.mock_cursor)

        self.mock_pool = MagicMock()
        self.mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=self.mock_conn)
        self.mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

        self.mock_checkpointer = MagicMock()
        self.mock_checkpointer.adelete_thread = AsyncMock()

        api.app.state.checkpointer = self.mock_checkpointer
        api.app.state.pool = self.mock_pool
        api.app.state.store = None

        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.checkpointer = None
        self.api.app.state.pool = None
        self.api.app.state.store = None
        self.client.close()

    def test_valid_uuid_returns_200_and_triggers_db_cleanup(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        response = self.client.delete(f"/api/memory/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "cleared")
        self.assertEqual(body["session_id"], session_id)

        self.mock_checkpointer.adelete_thread.assert_called_once_with(session_id)
        # Two statements: SELECT the user's thread ids, then DELETE store rows.
        self.assertEqual(self.mock_conn.execute.call_count, 2)
        select_sql = self.mock_conn.execute.call_args_list[0].args[0]
        self.assertIn("SELECT DISTINCT thread_id FROM traces WHERE user_id", select_sql)
        sql, params = self.mock_conn.execute.call_args_list[1].args
        self.assertIn("DELETE FROM store WHERE prefix LIKE", sql)
        self.assertIn(f"memories.{session_id}", params[0])

    def test_clear_memory_wipes_every_user_thread(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        thread_a = "11111111-1111-1111-1111-111111111111"
        self.mock_cursor.fetchall = AsyncMock(
            return_value=[{"thread_id": thread_a}, {"thread_id": session_id}]
        )

        response = self.client.delete(f"/api/memory/{session_id}")

        self.assertEqual(response.status_code, 200)
        deleted = {
            call.args[0]
            for call in self.mock_checkpointer.adelete_thread.call_args_list
        }
        self.assertEqual(deleted, {session_id, thread_a})

    def test_malformed_session_id_returns_400_and_no_db_access(self):
        response = self.client.delete("/api/memory/not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.mock_checkpointer.adelete_thread.assert_not_called()
        self.mock_conn.execute.assert_not_called()

    def test_bare_route_resolves(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        response = self.client.delete(f"/memory/{session_id}")
        self.assertEqual(response.status_code, 200)

    def test_degraded_mode_returns_200_without_raising(self):
        self.api.app.state.checkpointer = None
        self.api.app.state.pool = None
        session_id = "12345678-1234-1234-1234-123456789abc"
        response = self.client.delete(f"/api/memory/{session_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cleared")


class RunsEndpointTests(unittest.TestCase):
    def setUp(self):
        import api

        self.api = api
        api.RUNS.clear()
        api.RUN_ORDER.clear()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.pool = None
        self.api.RUNS.clear()
        self.api.RUN_ORDER.clear()
        self.client.close()

    def test_runs_empty_when_no_pool(self):
        self.api.app.state.pool = None
        response = self.client.get("/runs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"runs": []})

    def test_runs_scoped_by_session(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        rows = [
            {
                "run_id": "r1",
                "query": "first",
                "status": "success",
                "elapsed_ms": 120,
                "usage": {"providers": ["gemini"], "fallback_events": []},
                "created_at": datetime(2026, 7, 2, tzinfo=timezone.utc),
            },
            {
                "run_id": "r2",
                "query": "second",
                "status": "success",
                "elapsed_ms": 80,
                "usage": {
                    "providers": ["groq"],
                    "fallback_events": [{"provider": "gemini", "error": "boom"}],
                },
                "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
            },
        ]
        pool, conn = _stub_pool(fetchall_rows=rows)
        self.api.app.state.pool = pool

        response = self.client.get("/runs", headers={"X-Session-Id": session_id})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([r["run_id"] for r in body["runs"]], ["r1", "r2"])
        self.assertEqual(body["runs"][0]["provider"], "gemini")
        self.assertFalse(body["runs"][0]["has_fallback"])
        self.assertTrue(body["runs"][1]["has_fallback"])
        # The listing was scoped to the caller's user identity.
        sql = conn.execute.call_args.args[0]
        params = conn.execute.call_args.args[1]
        self.assertIn("WHERE user_id = %s", sql)
        self.assertIn(session_id, params)


class TraceEndpointTests(unittest.TestCase):
    def setUp(self):
        import api

        self.api = api
        api.RUNS.clear()
        api.RUN_ORDER.clear()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.pool = None
        self.api.RUNS.clear()
        self.api.RUN_ORDER.clear()
        self.client.close()

    def _db_row(self, run_id, answer):
        return {
            "run_id": run_id,
            "thread_id": "t1",
            "query": "q",
            "steps": [
                {
                    "thought": "t",
                    "action": "calculator",
                    "action_input": "1 + 1",
                    "observation": "2",
                    "timestamp": "2026-07-02T00:00:00+00:00",
                    "elapsed_ms": 3,
                }
            ],
            "final_answer": answer,
            "status": "success",
            "usage": {"providers": ["gemini"]},
            "elapsed_ms": 4200,
        }

    def _memory_response(self, run_id, answer):
        return self.api.AgentResponse(
            result=answer,
            trace=[],
            total_time=0.0,
            run_id=run_id,
            answer=answer,
            steps=[],
            tools_used=[],
            latency_ms=0,
            status="success",
            usage={},
        )

    def test_trace_db_first(self):
        run_id = "run-db"
        session_id = "12345678-1234-1234-1234-123456789abc"
        pool, conn = _stub_pool(
            fetchone_row=self._db_row(run_id=run_id, answer="from-db")
        )
        self.api.app.state.pool = pool
        # In-memory holds a different answer; the DB row must win.
        self.api.RUNS[run_id] = self._memory_response(run_id=run_id, answer="from-memory")

        response = self.client.get(
            f"/trace/{run_id}", headers={"X-Session-Id": session_id}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "from-db")
        self.assertEqual(body["run_id"], run_id)
        self.assertEqual(body["steps"][0]["elapsed_ms"], 3)
        # The DB lookup is scoped to the caller's session (T-4-05 hardening).
        self.assertEqual(conn.execute.call_args.args[1], (run_id, session_id))

    def test_trace_memory_fallback(self):
        run_id = "run-mem"
        pool, _conn = _stub_pool(fetchone_row=None)  # DB miss
        self.api.app.state.pool = pool
        self.api.RUNS[run_id] = self._memory_response(run_id=run_id, answer="from-memory")

        response = self.client.get(f"/trace/{run_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "from-memory")

    def test_trace_404(self):
        pool, _conn = _stub_pool(fetchone_row=None)
        self.api.app.state.pool = pool

        response = self.client.get("/trace/does-not-exist")

        self.assertEqual(response.status_code, 404)


class DocumentDeleteTests(unittest.TestCase):
    SESSION = "12345678-1234-1234-1234-123456789abc"
    DOC = "87654321-4321-4321-4321-cba987654321"

    def setUp(self):
        import api

        self.api = api
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.pool = None
        self.client.close()

    def _pool_with_rowcount(self, rowcount):
        pool, conn = _stub_pool()
        conn.execute.return_value.rowcount = rowcount
        return pool, conn

    def test_delete_scoped_to_session(self):
        pool, conn = self._pool_with_rowcount(1)
        self.api.app.state.pool = pool

        response = self.client.delete(f"/api/documents/{self.SESSION}/{self.DOC}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")
        sql, params = conn.execute.call_args.args
        self.assertIn("DELETE FROM documents WHERE id = %s AND session_id = %s", sql)
        self.assertEqual(params, (self.DOC, self.SESSION))

    def test_delete_unknown_doc_404(self):
        pool, _conn = self._pool_with_rowcount(0)
        self.api.app.state.pool = pool

        response = self.client.delete(f"/api/documents/{self.SESSION}/{self.DOC}")

        self.assertEqual(response.status_code, 404)

    def test_delete_invalid_ids_400(self):
        pool, conn = self._pool_with_rowcount(1)
        self.api.app.state.pool = pool

        for path in (
            f"/api/documents/not-a-uuid/{self.DOC}",
            f"/api/documents/{self.SESSION}/not-a-uuid",
        ):
            response = self.client.delete(path)
            self.assertEqual(response.status_code, 400)
        conn.execute.assert_not_called()

    def test_delete_no_pool_503(self):
        self.api.app.state.pool = None

        response = self.client.delete(f"/api/documents/{self.SESSION}/{self.DOC}")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
