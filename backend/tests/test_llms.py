import os
import unittest
from unittest.mock import patch

import httpx
from langchain_core.messages import HumanMessage


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

    def test_cloudflare_requires_account_id_and_token(self):
        from agent.llms import configured_free_providers

        with patch.dict(
            os.environ,
            {"REACT_AGENT_SKIP_DOTENV": "1", "CF_WORKERS_AI_TOKEN": "token-only"},
            clear=True,
        ):
            providers = configured_free_providers()

        self.assertEqual(providers, [])

    def test_fallback_error_redacts_configured_secret_values(self):
        from agent.llms import FreeModelFallback, FreeProvider

        secret = "test_gemini_fallback_secret"

        def failing_provider(messages):
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

    def test_http_status_errors_do_not_expose_query_secrets(self):
        from agent.llms import _raise_for_status

        secret = "test_gemini_status_error_secret"
        request = httpx.Request("POST", f"https://example.test/v1beta/model?key={secret}")
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
