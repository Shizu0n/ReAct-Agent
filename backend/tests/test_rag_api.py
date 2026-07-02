import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

VALID_SESSION = "12345678-1234-1234-1234-123456789abc"


def _list_pool(rows):
    """MagicMock pool whose connection() yields a conn whose execute returns a
    cursor with an AsyncMock fetchall."""
    cur = MagicMock()
    cur.fetchall = AsyncMock(return_value=rows)
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class UploadEndpointTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"
        import api
        self.api = api
        api.app.state.pool = MagicMock()  # truthy by default
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.pool = None
        self.client.close()

    def test_upload_returns_chunk_count(self):
        with patch("agent.ingest.ingest_document", new_callable=AsyncMock) as ingest:
            ingest.return_value = {
                "status": "ok",
                "filename": "r.txt",
                "chunks_stored": 3,
                "chunks_skipped": 0,
                "doc_id": "d1",
            }
            response = self.client.post(
                "/api/upload",
                files={"file": ("r.txt", b"hello content", "text/plain")},
                headers={"x-session-id": VALID_SESSION},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chunks_stored"], 3)

    def test_size_cap_returns_413(self):
        with patch("agent.ingest.ingest_document", new_callable=AsyncMock) as ingest:
            response = self.client.post(
                "/api/upload",
                files={"file": ("big.txt", b"x" * (2 * 1024 * 1024 + 1), "text/plain")},
                headers={"x-session-id": VALID_SESSION},
            )
        self.assertEqual(response.status_code, 413)
        ingest.assert_not_called()

    def test_unsupported_type_returns_415(self):
        with patch("agent.ingest.ingest_document", new_callable=AsyncMock) as ingest:
            response = self.client.post(
                "/api/upload",
                files={"file": ("archive.zip", b"PK\x03\x04data", "application/zip")},
                headers={"x-session-id": VALID_SESSION},
            )
        self.assertIn(response.status_code, (400, 415))
        ingest.assert_not_called()

    def test_pool_none_returns_503(self):
        self.api.app.state.pool = None
        response = self.client.post(
            "/api/upload",
            files={"file": ("r.txt", b"hello", "text/plain")},
            headers={"x-session-id": VALID_SESSION},
        )
        self.assertEqual(response.status_code, 503)


class DocumentListEndpointTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"
        import api
        self.api = api
        self.client = TestClient(api.app)

    def tearDown(self):
        self.api.app.state.pool = None
        self.client.close()

    def test_list_structure(self):
        created = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        rows = [
            {"id": "doc-1", "filename": "a.pdf", "created_at": created, "chunk_count": 5},
            {"id": "doc-2", "filename": "b.txt", "created_at": created, "chunk_count": 2},
        ]
        self.api.app.state.pool = _list_pool(rows)
        response = self.client.get(f"/api/documents/{VALID_SESSION}")
        self.assertEqual(response.status_code, 200)
        documents = response.json()["documents"]
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0]["chunk_count"], 5)
        self.assertIsInstance(documents[1]["chunk_count"], int)

    def test_invalid_session_400(self):
        self.api.app.state.pool = MagicMock()
        response = self.client.get("/api/documents/not-a-uuid")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
