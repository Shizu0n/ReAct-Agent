import asyncio
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from psycopg.types.json import Json

from agent.traces import _response_from_row, fetch_runs, fetch_trace, persist_trace


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


def _make_response(steps=None, answer="done", usage=None, status="success", latency_ms=1234):
    import api

    steps = steps if steps is not None else [
        {
            "thought": "think",
            "action": "calculator",
            "action_input": "1 + 1",
            "observation": "2",
            "timestamp": "2026-07-02T00:00:00+00:00",
            "elapsed_ms": 12,
        }
    ]
    return api.AgentResponse(
        result=answer,
        trace=steps,
        total_time=latency_ms / 1000,
        run_id="run-123",
        answer=answer,
        steps=steps,
        tools_used=["calculator"],
        latency_ms=latency_ms,
        status=status,
        usage=usage or {"providers": ["gemini"], "fallback_events": []},
    )


class PersistTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_persist_inserts_row(self):
        pool, conn = _stub_pool()
        response = _make_response()
        asyncio.run(
            persist_trace(pool, "run-123", "thread-9", "user-7", "what is 1 + 1", response)
        )

        conn.execute.assert_called_once()
        sql = conn.execute.call_args.args[0]
        params = conn.execute.call_args.args[1]

        self.assertIn("INSERT INTO traces", sql)
        self.assertIn("ON CONFLICT (run_id) DO NOTHING", sql)
        self.assertIn("%s", sql)
        # SQL is parameterized: no run_id / thread_id / query interpolated into it.
        self.assertNotIn("run-123", sql)
        self.assertNotIn("thread-9", sql)
        self.assertNotIn("what is 1 + 1", sql)

        self.assertIn("run-123", params)
        self.assertIn("thread-9", params)
        self.assertIn("user-7", params)
        self.assertIn("what is 1 + 1", params)
        # steps + usage are JSONB-wrapped for psycopg.
        json_params = [p for p in params if isinstance(p, Json)]
        self.assertEqual(len(json_params), 2)

    def test_persist_pool_none_is_noop(self):
        # Must not raise when the pool is unavailable.
        asyncio.run(persist_trace(None, "run-1", "thread-1", "user-1", "q", _make_response()))

    def test_persist_failure_is_catchable(self):
        pool = MagicMock()
        pool.connection.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            asyncio.run(
                persist_trace(pool, "run-1", "thread-1", "user-1", "q", _make_response())
            )


class RedactionTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"
        os.environ["TESTONLY_TRACE_SECRET_KEY"] = "supersecretvalue123"

    def tearDown(self):
        os.environ.pop("TESTONLY_TRACE_SECRET_KEY", None)

    def test_secret_not_stored(self):
        secret = "supersecretvalue123"
        steps = [
            {
                "thought": "think",
                "action": "web_search",
                "action_input": f"query with {secret}",
                "observation": f"leaked {secret} here",
                "timestamp": "2026-07-02T00:00:00+00:00",
                "elapsed_ms": 5,
            }
        ]
        response = _make_response(steps=steps, answer=f"the token is {secret}")
        pool, conn = _stub_pool()
        asyncio.run(persist_trace(pool, "run-1", "thread-1", "user-1", "q", response))

        params = conn.execute.call_args.args[1]
        steps_param = next(p for p in params if isinstance(p, Json))
        steps_dump = json.dumps(steps_param.obj)
        self.assertNotIn(secret, steps_dump)
        self.assertIn("[redacted]", steps_dump)

        final_answer = params[5]
        self.assertNotIn(secret, final_answer)
        self.assertIn("[redacted]", final_answer)

    def test_persist_does_not_mutate_live_response(self):
        secret = "supersecretvalue123"
        steps = [
            {
                "thought": "t",
                "action": "web_search",
                "action_input": "x",
                "observation": f"leaked {secret}",
                "timestamp": "2026-07-02T00:00:00+00:00",
                "elapsed_ms": 5,
            }
        ]
        response = _make_response(steps=steps, answer=f"tok {secret}")
        pool, _conn = _stub_pool()
        asyncio.run(persist_trace(pool, "run-1", "thread-1", "user-1", "q", response))
        # The live response objects must be untouched (only a redacted copy stored).
        self.assertIn(secret, response.steps[0]["observation"])
        self.assertIn(secret, response.answer)


class FetchTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_fetch_runs_scoped_and_ordered(self):
        rows = [
            {"run_id": "r1", "query": "q1", "status": "success",
             "elapsed_ms": 10, "usage": {}, "created_at": datetime.now(timezone.utc)},
        ]
        pool, conn = _stub_pool(fetchall_rows=rows)
        result = asyncio.run(fetch_runs(pool, "user-42"))

        self.assertEqual(result, rows)
        sql = conn.execute.call_args.args[0]
        params = conn.execute.call_args.args[1]
        self.assertIn("WHERE user_id = %s", sql)
        self.assertIn("ORDER BY created_at DESC", sql)
        self.assertIn("LIMIT", sql)
        self.assertIn("user-42", params)

    def test_fetch_runs_pool_none(self):
        self.assertEqual(asyncio.run(fetch_runs(None, "thread-1")), [])

    def test_fetch_trace_scoped_by_user(self):
        row = {"run_id": "r1", "steps": [], "final_answer": "x",
               "status": "success", "usage": {}, "elapsed_ms": 1}
        pool, conn = _stub_pool(fetchone_row=row)
        result = asyncio.run(fetch_trace(pool, "r1", "user-9"))

        self.assertEqual(result, row)
        sql = conn.execute.call_args.args[0]
        params = conn.execute.call_args.args[1]
        # The lookup is scoped to the owning user, not run_id alone (T-4-05).
        self.assertIn("WHERE run_id = %s AND user_id = %s", sql)
        self.assertEqual(params, ("r1", "user-9"))

    def test_fetch_trace_pool_none(self):
        self.assertIsNone(asyncio.run(fetch_trace(None, "r1", "thread-1")))

    def test_response_from_row(self):
        steps = [
            {
                "thought": "t",
                "action": "calculator",
                "action_input": "2 + 2",
                "observation": "4",
                "timestamp": "2026-07-02T00:00:00+00:00",
                "elapsed_ms": 7,
            }
        ]
        row = {
            "run_id": "run-abc",
            "thread_id": "thread-1",
            "query": "q",
            "steps": steps,
            "final_answer": "4",
            "status": "success",
            "usage": {"providers": ["groq"]},
            "elapsed_ms": 4200,
        }
        resp = _response_from_row(row)
        self.assertEqual(resp.result, "4")
        self.assertEqual(resp.answer, "4")
        self.assertEqual(resp.steps, steps)
        self.assertEqual(resp.steps[0]["elapsed_ms"], 7)
        self.assertEqual(resp.latency_ms, 4200)
        self.assertEqual(resp.tools_used, ["calculator"])
        self.assertEqual(resp.status, "success")


if __name__ == "__main__":
    unittest.main()
