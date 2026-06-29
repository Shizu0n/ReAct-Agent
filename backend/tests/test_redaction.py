import io
import logging
import os
import unittest
from unittest.mock import patch


class SecretRedactionTests(unittest.TestCase):
    def test_logging_redacts_env_secrets_in_message_args(self):
        from agent.redaction import install_secret_redaction

        secret = "test_logging_secret_value"
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("tests.secret_redaction")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        with patch.dict(os.environ, {"GEMINI_API_KEY": secret}, clear=True):
            install_secret_redaction()
            logger.info(
                'HTTP Request: POST %s "HTTP/1.1 200 OK"',
                f"https://example.test/models/gemini:generateContent?key={secret}",
            )
            logger.info("Authorization: Bearer %s", secret)

        output = stream.getvalue()
        self.assertNotIn(secret, output)
        self.assertIn("key=[redacted]", output)
        self.assertIn("Bearer [redacted]", output)

    def test_redact_secrets_scrubs_supabase_connection_string(self):
        from agent.redaction import redact_secrets

        fake_url = (
            "postgresql://postgres.abcdefghij:s3cr3tP4ssw0rd@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        )
        with patch.dict(os.environ, {"SUPABASE_POOLER_URL": fake_url}, clear=True):
            redacted = redact_secrets(f"connecting to {fake_url} now")

        self.assertNotIn(fake_url, redacted)
        self.assertNotIn("s3cr3tP4ssw0rd", redacted)
        self.assertIn("[redacted]", redacted)

    def test_secure_logging_quiets_noisy_access_loggers(self):
        from agent.redaction import configure_secure_logging

        configure_secure_logging()

        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)
        self.assertGreaterEqual(
            logging.getLogger("uvicorn.access").level, logging.WARNING
        )


if __name__ == "__main__":
    unittest.main()
