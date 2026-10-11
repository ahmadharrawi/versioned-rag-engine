-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for tracking versioned documents
-- effective_from: Inclusive timestamp when this document version became active.
-- effective_to: Exclusive timestamp when superseded. NULL indicates the latest active version.
CREATE TABLE IF NOT EXISTS doc_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(255) NOT NULL,
    version_number INT NOT NULL,
    title VARCHAR(512) NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT uq_doc_version UNIQUE (doc_id, version_number)
);

-- Table for versioned document text chunks and vector embeddings
-- all-mpnet-base-v2 produces 768-dimensional embeddings
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES doc_versions(version_id) ON DELETE CASCADE,
    doc_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for version validity lookups
CREATE INDEX IF NOT EXISTS idx_doc_versions_lookup 
ON doc_versions (doc_id, effective_from, effective_to);

-- Index for temporal joins from chunks to doc_versions
CREATE INDEX IF NOT EXISTS idx_chunks_version_id 
ON chunks (version_id);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id 
ON chunks (doc_id);

-- HNSW vector cosine similarity index for pgvector
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_cosine 
ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
