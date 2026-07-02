from __future__ import annotations

import asyncio

import httpx

from agent.redaction import redact_secrets

# gemini-embedding-001 batch endpoint. Same GEMINI_API_KEY as chat completions,
# passed as the x-goog-api-key header (mirrors the provider path in llms.py).
EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-embedding-001:batchEmbedContents"
)
EMBED_BATCH_SIZE = 100  # hard API limit: at most 100 requests per batch call
EMBED_MAX_RETRIES = 3
EMBED_DIM = 768  # matches document_chunks.embedding vector(768)


async def embed_batch(texts: list[str], api_key: str) -> list[list[float]]:
    """Embed up to EMBED_BATCH_SIZE texts via gemini-embedding-001.

    Retries with exponential backoff on HTTP 429 (rate limit). Any other HTTP
    error, or exhausting EMBED_MAX_RETRIES, raises a RuntimeError whose message
    passes the provider body through redact_secrets.
    """
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    payload = {
        "requests": [
            {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
                "embedContentConfig": {"outputDimensionality": EMBED_DIM},
            }
            for text in texts
        ]
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    last_error = ""
    for attempt in range(EMBED_MAX_RETRIES):
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(EMBED_URL, json=payload, headers=headers)
        if response.status_code == 429:
            last_error = "HTTP 429 (rate limited)"
            await asyncio.sleep(min(2 ** attempt, 30))
            continue
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = redact_secrets(exc.response.text[:500]).strip()
            raise RuntimeError(
                f"Embedding request failed (HTTP {response.status_code}): {detail}"
            ) from None
        data = response.json()
        vectors = [item["values"] for item in data["embeddings"]]
        for vector in vectors:
            if len(vector) != EMBED_DIM:
                raise RuntimeError(
                    f"Embedding dimension mismatch: expected {EMBED_DIM}, got {len(vector)}"
                )
        return vectors
    raise RuntimeError(
        f"Embedding failed after {EMBED_MAX_RETRIES} retries: {last_error}"
    )


async def embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    """Embed all texts in batches of EMBED_BATCH_SIZE, preserving input order."""
    results: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        results.extend(await embed_batch(batch, api_key))
    return results


async def embed_query(text: str, api_key: str) -> list[float]:
    """Embed a single query string (used by document_search retrieval)."""
    return (await embed_texts([text], api_key))[0]
