"""Tests for long-term memory helpers (_run_memory_read, _run_memory_write).

Uses FakeStore — an in-memory async store that mirrors the AsyncPostgresStore
interface (asearch returns items newest-first, aput/adelete mutate in-place).
No real DB connection required.
"""
import asyncio
import os
import unittest


# ---------------------------------------------------------------------------
# FakeStore infrastructure
# ---------------------------------------------------------------------------

class _FakeItem:
    """Minimal store item exposing .key and .value like AsyncPostgresStore items."""

    def __init__(self, key: str, value: dict, order: int) -> None:
        self.key = key
        self.value = value
        self._order = order  # higher = newer (insertion counter)


class FakeStore:
    """Async in-memory store whose asearch returns items newest-first."""

    def __init__(self) -> None:
        self._data: dict = {}   # {namespace_tuple: {key: _FakeItem}}
        self._counter: int = 0

    async def asearch(self, namespace, limit: int = 20, **kwargs):
        ns = tuple(namespace)
        items = list(self._data.get(ns, {}).values())
        items.sort(key=lambda x: x._order, reverse=True)  # newest first
        return items[:limit]

    async def aput(self, namespace, key: str, value: dict) -> None:
        ns = tuple(namespace)
        if ns not in self._data:
            self._data[ns] = {}
        self._counter += 1
        self._data[ns][key] = _FakeItem(key=key, value=value, order=self._counter)

    async def adelete(self, namespace, key: str) -> None:
        ns = tuple(namespace)
        if ns in self._data and key in self._data[ns]:
            del self._data[ns][key]

    def _count(self, namespace) -> int:
        """Return number of items stored under namespace (for assertions)."""
        return len(self._data.get(tuple(namespace), {}))

    def _keys(self, namespace) -> set:
        """Return set of keys under namespace."""
        return set(self._data.get(tuple(namespace), {}).keys())


# ---------------------------------------------------------------------------
# Helper: run async coroutine from sync test context
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class LongTermMemoryTests(unittest.TestCase):
    """MEM-03: Agent can write and then read back a fact."""

    def setUp(self):
        self.store = FakeStore()
        self.session = "test-session-1"

    def test_write_then_read_returns_fact_inside_barrier(self):
        from agent.graph import _run_memory_read, _run_memory_write

        run(_run_memory_write(self.store, self.session, "My dog is named Rex"))
        result = run(_run_memory_read(self.store, self.session, "dog"))

        self.assertIn("Rex", result)
        self.assertIn("--- BEGIN USER MEMORIES ---", result)
        self.assertIn("--- END USER MEMORIES ---", result)

    def test_multiple_writes_all_recalled(self):
        from agent.graph import _run_memory_read, _run_memory_write

        run(_run_memory_write(self.store, self.session, "I prefer Python"))
        run(_run_memory_write(self.store, self.session, "I live in Sao Paulo"))

        result = run(_run_memory_read(self.store, self.session, "preferences"))

        self.assertIn("Python", result)
        self.assertIn("Sao Paulo", result)

    def test_read_empty_store_returns_no_memories_message(self):
        from agent.graph import _run_memory_read

        result = run(_run_memory_read(self.store, self.session, "anything"))

        self.assertIn("No memories", result)
        self.assertNotIn("BEGIN USER MEMORIES", result)

    def test_write_blank_content_is_a_noop(self):
        from agent.graph import _run_memory_read, _run_memory_write

        run(_run_memory_write(self.store, self.session, ""))
        run(_run_memory_write(self.store, self.session, "   "))

        self.assertEqual(self.store._count(("memories", self.session)), 0)
        result = run(_run_memory_read(self.store, self.session, "anything"))
        self.assertNotIn("BEGIN USER MEMORIES", result)

    def test_session_namespacing_isolates_memories(self):
        from agent.graph import _run_memory_read, _run_memory_write

        run(_run_memory_write(self.store, "session-A", "Fact for A"))
        run(_run_memory_write(self.store, "session-B", "Fact for B"))

        result_a = run(_run_memory_read(self.store, "session-A", "anything"))
        result_b = run(_run_memory_read(self.store, "session-B", "anything"))

        self.assertIn("Fact for A", result_a)
        self.assertNotIn("Fact for B", result_a)
        self.assertIn("Fact for B", result_b)
        self.assertNotIn("Fact for A", result_b)


class MemoryCapTests(unittest.TestCase):
    """MEM-07: Stored memory per session is capped at MAX_MEMORIES_STORED."""

    def setUp(self):
        self.store = FakeStore()
        self.session = "cap-test-session"

    def test_store_never_exceeds_cap(self):
        from agent.graph import MAX_MEMORIES_STORED, _run_memory_write

        extra = 2
        total_writes = MAX_MEMORIES_STORED + extra

        for i in range(total_writes):
            run(_run_memory_write(self.store, self.session, f"fact-{i}"))

        ns = ("memories", self.session)
        self.assertEqual(self.store._count(ns), MAX_MEMORIES_STORED)

    def test_oldest_entries_evicted_first(self):
        from agent.graph import MAX_MEMORIES_STORED, _run_memory_read, _run_memory_write

        # Write exactly cap+2 facts; the first two should be evicted.
        total_writes = MAX_MEMORIES_STORED + 2
        # Use zero-padded IDs to avoid substring false-positives (e.g. "fact-01"
        # is not a substring of "fact-010" when left-padded to 3 digits).
        facts = [f"unique-fact-{i:03d}" for i in range(total_writes)]
        for fact in facts:
            run(_run_memory_write(self.store, self.session, fact))

        result = run(_run_memory_read(self.store, self.session, "anything"))
        # Parse recalled facts from the barrier lines to avoid substring false-positives.
        recalled = {
            line.lstrip("- ").strip()
            for line in result.split("\n")
            if line.strip().startswith("-")
        }

        # The 2 oldest (facts[0] and facts[1]) must be gone.
        self.assertNotIn(facts[0], recalled)
        self.assertNotIn(facts[1], recalled)
        # The newest fact must be present.
        self.assertIn(facts[-1], recalled)

    def test_write_at_exactly_cap_evicts_oldest(self):
        from agent.graph import MAX_MEMORIES_STORED, _run_memory_write

        for i in range(MAX_MEMORIES_STORED):
            run(_run_memory_write(self.store, self.session, f"existing-{i}"))

        ns = ("memories", self.session)
        self.assertEqual(self.store._count(ns), MAX_MEMORIES_STORED)

        # One more write should evict exactly one.
        run(_run_memory_write(self.store, self.session, "new-fact"))
        self.assertEqual(self.store._count(ns), MAX_MEMORIES_STORED)


class DegradedStoreTests(unittest.TestCase):
    """store=None path: tool_node returns a graceful observation without raising."""

    def test_memory_read_with_none_store_via_tool_node(self):
        """tool_node with store=None returns graceful unavailable message for memory_read."""
        import asyncio as _asyncio
        from agent.graph import MEMORY_READ_TOOL_NAME, tool_node
        from langchain_core.messages import AIMessage

        def make_tool_call(name, **args):
            return AIMessage(
                content="", tool_calls=[{"name": name, "args": args, "id": "tc-1"}]
            )

        state = {
            "messages": [make_tool_call(MEMORY_READ_TOOL_NAME, query="test")],
            "intermediate_steps": [],
            "iteration_count": 0,
            "final_answer": None,
        }
        config = {"configurable": {"thread_id": "degraded-session"}}

        result = _asyncio.run(tool_node(state, None, config))

        step = result["intermediate_steps"][-1]
        self.assertIn("unavailable", step["observation"].lower())
        # Step must still have all required keys.
        self.assertEqual(
            set(step.keys()),
            {"thought", "action", "action_input", "observation", "timestamp"},
        )

    def test_memory_write_with_none_store_via_tool_node(self):
        """tool_node with store=None returns graceful unavailable message for memory_write."""
        import asyncio as _asyncio
        from agent.graph import MEMORY_WRITE_TOOL_NAME, tool_node
        from langchain_core.messages import AIMessage

        def make_tool_call(name, **args):
            return AIMessage(
                content="", tool_calls=[{"name": name, "args": args, "id": "tc-2"}]
            )

        state = {
            "messages": [make_tool_call(MEMORY_WRITE_TOOL_NAME, content="some fact")],
            "intermediate_steps": [],
            "iteration_count": 0,
            "final_answer": None,
        }
        config = {"configurable": {"thread_id": "degraded-session"}}

        result = _asyncio.run(tool_node(state, None, config))

        step = result["intermediate_steps"][-1]
        self.assertIn("unavailable", step["observation"].lower())
        self.assertEqual(
            set(step.keys()),
            {"thought", "action", "action_input", "observation", "timestamp"},
        )


if __name__ == "__main__":
    unittest.main()
