from __future__ import annotations

import io
import os
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from agent.embedding import embed_texts

MAX_CHUNKS = 200  # bounds embedding batch calls (<=2) and DB inserts per document

# Zero-width, directional-formatting, word-joiner, deprecated-formatting,
# soft-hyphen, Mongolian-vowel-separator, and BOM codepoints. Stripped before
# chunking so invisible-character injection payloads never reach storage.
_INVISIBLE_RE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u206a-\u206f\u00ad\u180e\ufeff]"
)

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
    separators=["\n\n", "\n", " ", ""],
)


def strip_invisible(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text(filename: str, content: bytes, content_type: str) -> str:
    content_type = (content_type or "").lower()
    name = (filename or "").lower()
    if "pdf" in content_type or name.endswith(".pdf"):
        return extract_pdf_text(content)
    return content.decode("utf-8", errors="replace")


async def ingest_document(
    pool, session_id: str, filename: str, content: bytes, content_type: str
) -> dict:
    """Extract -> strip_invisible -> chunk -> cap -> embed -> insert.

    Returns {status, filename, chunks_stored, chunks_skipped, doc_id}. Never
    writes the uploaded bytes to disk (Vercel's filesystem is ephemeral) - only
    the extracted text and its embeddings are persisted to Supabase.
    """
    text = strip_invisible(extract_text(filename, content, content_type))
    all_chunks = _SPLITTER.split_text(text)
    total = len(all_chunks)
    chunks = all_chunks[:MAX_CHUNKS]
    chunks_skipped = max(0, total - MAX_CHUNKS)

    if not chunks:
        return {
            "status": "empty",
            "filename": filename,
            "chunks_stored": 0,
            "chunks_skipped": chunks_skipped,
            "doc_id": "",
        }

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured for document ingestion")

    vectors = await embed_texts(chunks, api_key)

    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            INSERT INTO documents (session_id, filename, mime_type, byte_size)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (session_id, filename, content_type or "", len(content)),
        )
        row = await cur.fetchone()
        doc_id = row["id"]
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            vec_str = "[" + ",".join(str(round(x, 8)) for x in vector) + "]"
            await conn.execute(
                """
                INSERT INTO document_chunks
                    (document_id, session_id, chunk_index, content, embedding, token_count)
                VALUES (%s, %s, %s, %s, %s::vector(768), %s)
                """,
                (doc_id, session_id, idx, chunk, vec_str, len(chunk.split())),
            )

    return {
        "status": "truncated" if total > MAX_CHUNKS else "ok",
        "filename": filename,
        "chunks_stored": len(chunks),
        "chunks_skipped": chunks_skipped,
        "doc_id": str(doc_id),
    }
