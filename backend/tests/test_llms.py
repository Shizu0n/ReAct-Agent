import os
import unittest
from unittest.mock import patch

import httpx
from langchain_core.messages import AIMessage, HumanMessage


class LlmSelectionTests(unittest.TestCase):
    def test_default_llm_ignores_openai_and_anthropic_keys(self):
        from agent.graph import _create_default_llm

        env = {
            "REACT_AGENT_SKIP_DOTENV": "1",
            "OPENAI_API_KEY": "paid-openai-key",
            "ANTHROPIC_API_KEY": "paid-anthropic-key",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as context:
                _create_default_llm()

        self.assertIn("free", str(context.exception).lower())
        self.assertNotIn("OPENAI_API_KEY", str(context.exception))
        self.assertNotIn("ANTHROPIC_API_KEY", str(context.exception))

    def test_default_llm_uses_free_provider_fallback_chain(self):
        from agent.graph import _create_default_llm
        from agent.llms import FreeModelFallback

        with patch.dict(
            os.environ,
            {"REACT_AGENT_SKIP_DOTENV": "1", "GROQ_API_KEY": "free-tier-key"},
            clear=True,
        ):
            llm = _create_default_llm()

        self.assertIsInstance(llm, FreeModelFallback)
        self.assertEqual([provider.name for provider in llm.providers], ["groq"])

    def test_only_gemini_groq_github_providers_are_supported(self):
        from agent.llms import configured_free_providers

        # Cloudflare and OpenRouter were removed; their env vars must be ignored.
        with patch.dict(
            os.environ,
            {
                "REACT_AGENT_SKIP_DOTENV": "1",
                "CF_ACCOUNT_ID": "acct",
                "CF_WORKERS_AI_TOKEN": "token",
                "OPENROUTER_API_KEY": "router-key",
                "GROQ_API_KEY": "free-tier-key",
            },
            clear=True,
        ):
            providers = configured_free_providers()

        self.assertEqual([provider.name for provider in providers], ["groq"])

    def test_fallback_error_redacts_configured_secret_values(self):
        from agent.llms import FreeModelFallback, FreeProvider

        secret = "test_gemini_fallback_secret"

        def failing_provider(messages, tools=None):
            raise RuntimeError(
                "403 calling https://example.test/models/foo:generateContent?key="
                f"{secret}"
            )

        with patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True):
            fallback = FreeModelFallback([FreeProvider("gemini", failing_provider)])
            with self.assertRaises(RuntimeError) as context:
                fallback.invoke([HumanMessage(content="hello")])

        message = str(context.exception)
        self.assertNotIn(secret, message)
        self.assertIn("key=[redacted]", message)

    def test_usage_tracker_aggregates_tokens_and_estimated_cost(self):
        from agent.llms import UsageTracker

        tracker = UsageTracker()
        message = AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
            },
            response_metadata={
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "latency_ms": 900,
            },
        )
        tracker.record(message)
        tracker.record(message)
        summary = tracker.summary()

        self.assertEqual(summary["llm_calls"], 2)
        self.assertEqual(summary["input_tokens"], 2000)
        self.assertEqual(summary["total_tokens"], 3000)
        self.assertEqual(summary["providers"], ["gemini"])
        # Per call: (1000 * 0.30 + 500 * 2.50) / 1e6 = 0.00155; two calls = 0.0031.
        self.assertAlmostEqual(summary["estimated_cost_usd"], 0.0031, places=6)

    def test_recovers_groq_tool_use_failed_into_tool_call(self):
        from agent.llms import _recover_tool_use_failed

        # Exact shapes Groq's llama-3.3 emitted (note the stray extra brace).
        cases = [
            '<function=calculator {"expression": "17 * 23 + math.sqrt(1764)"} </function>',
            '<function=python_executor{"code": "print(sum([i**2 for i in range(1, 21)]))"}}</function>',
        ]
        for generation in cases:
            response = httpx.Response(
                400,
                request=httpx.Request("POST", "https://api.groq.test/v1"),
                json={"error": {"code": "tool_use_failed", "failed_generation": generation}},
            )
            recovered = _recover_tool_use_failed(response)
            self.assertIsNotNone(recovered)
            self.assertEqual(len(recovered.tool_calls), 1)

        first = _recover_tool_use_failed(
            httpx.Response(
                400,
                request=httpx.Request("POST", "https://api.groq.test/v1"),
                json={"error": {"code": "tool_use_failed", "failed_generation": cases[0]}},
            )
        )
        self.assertEqual(first.tool_calls[0]["name"], "calculator")
        self.assertEqual(
            first.tool_calls[0]["args"]["expression"], "17 * 23 + math.sqrt(1764)"
        )

    def test_tool_use_recovery_ignores_unrelated_400(self):
        from agent.llms import _recover_tool_use_failed

        response = httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.groq.test/v1"),
            json={"error": {"code": "invalid_request_error", "message": "bad model"}},
        )
        self.assertIsNone(_recover_tool_use_failed(response))

    def test_http_status_errors_do_not_expose_query_secrets(self):
        from agent.llms import _raise_for_status

        secret = "test_gemini_status_error_secret"
        request = httpx.Request(
            "POST", f"https://example.test/v1beta/model?key={secret}"
        )
        response = httpx.Response(
            403,
            request=request,
            text='{"error":"invalid api key"}',
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True):
            with self.assertRaises(RuntimeError) as context:
                _raise_for_status(response, "gemini")

        message = str(context.exception)
        self.assertNotIn(secret, message)
        self.assertNotIn("example.test/v1beta/model?key=", message)
        self.assertIn("HTTP 403", message)


if __name__ == "__main__":
    unittest.main()
