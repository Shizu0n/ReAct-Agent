-- migration.sql
-- Enable pgvector (pre-installed on Supabase; just needs enabling)
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: tracks uploaded files per session
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    filename    TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    byte_size   INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS documents_session_idx ON documents (session_id);

-- Document chunks: text + embedding storage for RAG (Phase 3)
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    session_id   TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(768),        -- gemini-embedding-001 with output_dimensionality=768
    token_count  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS chunks_session_idx  ON document_chunks (session_id);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON document_chunks (document_id);

-- HNSW index on embedding column (cosine distance for semantic similarity)
-- Create AFTER table, before or after data (HNSW works either way)
-- m=16, ef_construction=64 are the pgvector defaults; fine for <10K vectors
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Traces table: persisted agent run traces for observability (Phase 4)
CREATE TABLE IF NOT EXISTS traces (
    run_id      TEXT PRIMARY KEY,
    thread_id   TEXT,
    query       TEXT,
    steps       JSONB,
    final_answer TEXT,
    status      TEXT,
    usage       JSONB,
    elapsed_ms  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS traces_thread_idx  ON traces (thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS traces_created_idx ON traces (created_at DESC);

-- Keepalive table: single-row ping target for Vercel cron
CREATE TABLE IF NOT EXISTS keepalive (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    pinged_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Seed with the single row (idempotent)
INSERT INTO keepalive (id, pinged_at)
VALUES (1, NOW())
ON CONFLICT (id) DO NOTHING;

-- Enforce single-row constraint (belt-and-suspenders)
CREATE UNIQUE INDEX IF NOT EXISTS keepalive_singleton ON keepalive (id);
