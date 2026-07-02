import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from agent.graph import DOCUMENT_SEARCH_TOOL_NAME, _run_document_search, tool_node


def _pool_with_rows(rows):
    """MagicMock pool whose connection() yields a conn whose execute returns a
    cursor with an AsyncMock fetchall returning `rows`."""
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=rows)
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


def _search_call_state(query="what is in the file"):
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": DOCUMENT_SEARCH_TOOL_NAME, "args": {"query": query}, "id": "tc-1"}
                ],
            )
        ],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }


class DocumentSearchStepTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_step_shape(self):
        rows = [
            {"content": "alpha", "filename": "a.pdf", "chunk_index": 0},
            {"content": "beta", "filename": "a.pdf", "chunk_index": 1},
        ]
        pool, _conn = _pool_with_rows(rows)
        config = {"configurable": {"thread_id": "sess-1"}}
        with patch("agent.embedding.embed_query", new_callable=AsyncMock) as eq:
            eq.return_value = [0.1] * 768
            result = asyncio.run(tool_node(_search_call_state(), None, config, pool=pool))
        step = result["intermediate_steps"][-1]
        self.assertEqual(
            set(step.keys()),
            {"thought", "action", "action_input", "observation", "timestamp"},
        )
        self.assertEqual(step["action"], "document_search")


class CitationTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_citation_format(self):
        rows = [
            {"content": "John is an engineer.", "filename": "resume.pdf", "chunk_index": 2},
            {"content": "John worked at X.", "filename": "resume.pdf", "chunk_index": 6},
        ]
        pool, _conn = _pool_with_rows(rows)
        with patch("agent.embedding.embed_query", new_callable=AsyncMock) as eq:
            eq.return_value = [0.1] * 768
            obs = asyncio.run(_run_document_search(pool, "sess-1", "who is John"))
        self.assertIn("[Source: resume.pdf, chunk 3]", obs)
        self.assertIn("[Source: resume.pdf, chunk 7]", obs)
        self.assertIn("--- BEGIN RETRIEVED DOCUMENTS ---", obs)
        self.assertIn("--- END RETRIEVED DOCUMENTS ---", obs)


class NoResultTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_no_docs(self):
        pool, _conn = _pool_with_rows([])
        with patch("agent.embedding.embed_query", new_callable=AsyncMock) as eq:
            eq.return_value = [0.1] * 768
            obs = asyncio.run(_run_document_search(pool, "sess-1", "anything"))
        self.assertNotIn("--- BEGIN RETRIEVED DOCUMENTS ---", obs)
        self.assertIn("No relevant content", obs)

    def test_pool_none(self):
        config = {"configurable": {"thread_id": "sess-1"}}
        result = asyncio.run(tool_node(_search_call_state(), None, config, pool=None))
        observation = result["intermediate_steps"][-1]["observation"]
        self.assertIn("unavailable", observation.lower())


class SessionScopeTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_query_filters_session(self):
        rows = [{"content": "x", "filename": "a.pdf", "chunk_index": 0}]
        pool, conn = _pool_with_rows(rows)
        with patch("agent.embedding.embed_query", new_callable=AsyncMock) as eq:
            eq.return_value = [0.1] * 768
            asyncio.run(_run_document_search(pool, "sess-42", "q"))
        sql = conn.execute.call_args.args[0]
        params = conn.execute.call_args.args[1]
        self.assertIn("dc.session_id = %s", sql)
        self.assertIn("<=>", sql)
        self.assertIn("sess-42", params)


if __name__ == "__main__":
    unittest.main()
