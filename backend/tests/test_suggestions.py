import os
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.suggestions import FALLBACK_SUGGESTIONS, generate_suggestions


class ScriptedLLM:
    """Returns a queued response per invoke; records the messages it received."""

    def __init__(self, response):
        self._response = response
        self.calls = []

    def invoke(self, messages, tools=None):
        self.calls.append(messages)
        return self._response if isinstance(self._response, AIMessage) else AIMessage(
            content=self._response
        )


class RaisingLLM:
    def invoke(self, messages, tools=None):
        raise RuntimeError("provider exploded")


HISTORY = [
    {"role": "user", "content": "What is the latest Python version?"},
    {"role": "assistant", "content": "Python 3.13.7 is the latest stable release."},
]
TOOLS = ["web_search", "python_executor", "calculator"]


class GenerateSuggestionsTests(unittest.TestCase):
    def test_parses_valid_json_object(self):
        llm = ScriptedLLM(
            '{"suggestions": ["Verify 3.13.7 against python.org", '
            '"List what changed in 3.13"]}'
        )

        result = generate_suggestions(HISTORY, TOOLS, llm=llm)

        self.assertEqual(
            result,
            ["Verify 3.13.7 against python.org", "List what changed in 3.13"],
        )

    def test_passes_tool_list_into_prompt(self):
        llm = ScriptedLLM('{"suggestions": ["a"]}')

        generate_suggestions(HISTORY, TOOLS, tools_used=["web_search"], llm=llm)

        system_text = str(llm.calls[0][0].content)
        for tool in TOOLS:
            self.assertIn(tool, system_text)

    def test_caps_and_dedupes_suggestions(self):
        llm = ScriptedLLM(
            '{"suggestions": ["one", "ONE", "two", "three", "four"]}'
        )

        result = generate_suggestions(HISTORY, TOOLS, llm=llm)

        self.assertEqual(result, ["one", "two", "three"])

    def test_malformed_json_falls_back(self):
        llm = ScriptedLLM("Sure! Here are some ideas, no JSON though.")

        result = generate_suggestions(HISTORY, TOOLS, llm=llm)

        self.assertEqual(result, FALLBACK_SUGGESTIONS)

    def test_provider_error_falls_back(self):
        result = generate_suggestions(HISTORY, TOOLS, llm=RaisingLLM())

        self.assertEqual(result, FALLBACK_SUGGESTIONS)

    def test_empty_history_skips_llm_and_falls_back(self):
        llm = ScriptedLLM('{"suggestions": ["should not be used"]}')

        result = generate_suggestions([], TOOLS, llm=llm)

        self.assertEqual(result, FALLBACK_SUGGESTIONS)
        self.assertEqual(llm.calls, [])

    def test_no_configured_provider_falls_back(self):
        with patch.dict(
            os.environ, {"REACT_AGENT_SKIP_DOTENV": "1"}, clear=True
        ):
            result = generate_suggestions(HISTORY, TOOLS)

        self.assertEqual(result, FALLBACK_SUGGESTIONS)


if __name__ == "__main__":
    unittest.main()
