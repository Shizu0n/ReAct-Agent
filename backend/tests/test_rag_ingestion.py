import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import ingest
from agent.embedding import (
    EMBED_BATCH_SIZE,
    EMBED_DIM,
    EMBED_MAX_RETRIES,
    embed_batch,
    embed_texts,
)
from agent.ingest import ingest_document, strip_invisible


def _mk_response(status, payload=None):
    """Build a stand-in httpx.Response with the status/json a test needs."""
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload if payload is not None else {}
    return response


def _mock_pool():
    """A MagicMock pool whose connection() yields an AsyncMock-backed conn.

    conn.execute returns a cursor whose fetchone yields a documents row id;
    the same cursor is returned for every execute (chunk inserts ignore it).
    """
    cur = MagicMock()
    cur.fetchone = AsyncMock(return_value={"id": "doc-123"})
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cur)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection = MagicMock(return_value=cm)
    return pool, conn


def _sqls(conn):
    return [str(call.args[0]).lower() for call in conn.execute.call_args_list]


class StripInvisibleTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_strips_zero_width(self):
        # zero-width space, zero-width joiner, BOM, soft hyphen interleaved
        # (explicit escapes so the test is deterministic and scanner-clean).
        raw = "a\u200bb\u200dc\ufeffd\u00ade"
        self.assertEqual(strip_invisible(raw), "abcde")


class ChunkingTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_chunk_params(self):
        self.assertEqual(ingest._SPLITTER._chunk_size, 500)
        self.assertEqual(ingest._SPLITTER._chunk_overlap, 50)

    def test_caps_at_200_chunks(self):
        pool, _conn = _mock_pool()
        big_text = "word " * 30000  # ~150k chars -> well over 200 chunks
        with patch("agent.ingest.embed_texts", new_callable=AsyncMock) as embed, \
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            embed.side_effect = lambda chunks, key: [[0.1] * EMBED_DIM for _ in chunks]
            result = asyncio.run(
                ingest_document(pool, "s1", "big.txt", big_text.encode(), "text/plain")
            )
        self.assertEqual(result["chunks_stored"], ingest.MAX_CHUNKS)
        self.assertGreater(result["chunks_skipped"], 0)
        self.assertEqual(result["status"], "truncated")


class EmbedBatchTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_backoff_then_success(self):
        ok = _mk_response(200, {"embeddings": [{"values": [0.1] * EMBED_DIM}]})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post, \
                patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            post.side_effect = [_mk_response(429), ok]
            vectors = asyncio.run(embed_batch(["hello"], "test-key"))
        self.assertEqual(len(vectors), 1)
        self.assertEqual(len(vectors[0]), EMBED_DIM)
        self.assertEqual(sleep.call_count, 1)

    def test_max_retries_raises(self):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post, \
                patch("asyncio.sleep", new_callable=AsyncMock):
            post.return_value = _mk_response(429)
            with self.assertRaises(RuntimeError):
                asyncio.run(embed_batch(["hello"], "test-key"))

    def test_batches_of_100(self):
        with patch("agent.embedding.embed_batch", new_callable=AsyncMock) as batch:
            batch.side_effect = lambda texts, key: [[0.0] * EMBED_DIM for _ in texts]
            result = asyncio.run(embed_texts(["t"] * 150, "test-key"))
        self.assertEqual(batch.call_count, 2)
        self.assertEqual(len(result), 150)
        self.assertEqual(EMBED_BATCH_SIZE, 100)


class IngestTests(unittest.TestCase):
    def setUp(self):
        os.environ["REACT_AGENT_SKIP_DOTENV"] = "1"

    def test_pipeline_inserts_document_and_chunks(self):
        pool, conn = _mock_pool()
        with patch("agent.ingest.embed_texts", new_callable=AsyncMock) as embed, \
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            embed.side_effect = lambda chunks, key: [[0.1] * EMBED_DIM for _ in chunks]
            result = asyncio.run(
                ingest_document(
                    pool, "s1", "note.txt", b"Hello world. A short note.", "text/plain"
                )
            )
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["chunks_stored"], 0)
        self.assertTrue(result["doc_id"])
        sqls = _sqls(conn)
        doc_inserts = [s for s in sqls if "insert into documents" in s]
        chunk_inserts = [s for s in sqls if "insert into document_chunks" in s]
        self.assertEqual(len(doc_inserts), 1)
        self.assertEqual(len(chunk_inserts), result["chunks_stored"])

    def test_pdf_uses_pypdf(self):
        pool, conn = _mock_pool()
        page = MagicMock()
        page.extract_text.return_value = "Known PDF text content."
        fake_reader = MagicMock()
        fake_reader.pages = [page]
        with patch("agent.ingest.PdfReader", return_value=fake_reader) as reader, \
                patch("agent.ingest.embed_texts", new_callable=AsyncMock) as embed, \
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            embed.side_effect = lambda chunks, key: [[0.1] * EMBED_DIM for _ in chunks]
            result = asyncio.run(
                ingest_document(pool, "s1", "r.pdf", b"%PDF-fake", "application/pdf")
            )
        reader.assert_called_once()
        self.assertGreater(result["chunks_stored"], 0)
        chunk_contents = " ".join(
            str(call.args[1][3])
            for call in conn.execute.call_args_list
            if "insert into document_chunks" in str(call.args[0]).lower()
        )
        self.assertIn("Known PDF text", chunk_contents)

    def test_missing_api_key_raises(self):
        pool, _conn = _mock_pool()
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(
                    ingest_document(pool, "s1", "n.txt", b"some content here", "text/plain")
                )
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
