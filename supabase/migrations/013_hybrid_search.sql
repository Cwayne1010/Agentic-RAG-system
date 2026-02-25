-- Migration 013: Hybrid Search Support - Add full-text search index for BM25
--
-- Adds GIN index on document_chunks.content to enable PostgreSQL's built-in
-- full-text search capabilities alongside existing pgvector semantic search.
-- This supports hybrid search (BM25 + vector) with Reciprocal Rank Fusion.
--
-- Run in Supabase SQL editor before implementing Module 6 hybrid search.

-- Create GIN index for full-text search on content column
-- This enables fast BM25-style keyword search using PostgreSQL's tsvector
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_fts
ON document_chunks
USING gin (to_tsvector('english', content));

-- Optional: Add materialized tsvector column for even faster searches
-- Uncomment these if performance testing shows it's needed:
--
-- ALTER TABLE document_chunks ADD COLUMN content_tsvector tsvector;
-- UPDATE document_chunks SET content_tsvector = to_tsvector('english', content);
-- CREATE INDEX idx_document_chunks_tsvector ON document_chunks USING gin (content_tsvector);
--
-- -- Trigger to keep tsvector updated
-- CREATE OR REPLACE FUNCTION update_content_tsvector()
-- RETURNS trigger AS $$
-- BEGIN
--     NEW.content_tsvector := to_tsvector('english', NEW.content);
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;
--
-- CREATE TRIGGER trigger_update_content_tsvector
--     BEFORE INSERT OR UPDATE ON document_chunks
--     FOR EACH ROW EXECUTE FUNCTION update_content_tsvector();

-- Create RPC function for BM25-style full-text search
-- Returns ranked results with ts_rank score
CREATE OR REPLACE FUNCTION bm25_search_chunks(
    query_text TEXT,
    match_count INT DEFAULT 20,
    filter_doc_type TEXT DEFAULT NULL
)
RETURNS TABLE(
    chunk_id UUID,
    content TEXT,
    doc_filename TEXT,
    chunk_index INT,
    document_id UUID,
    doc_metadata JSONB,
    bm25_score REAL
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT
        dc.id as chunk_id,
        dc.content,
        d.filename as doc_filename,
        dc.chunk_index,
        dc.document_id,
        d.metadata as doc_metadata,
        ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', query_text))::REAL as bm25_score
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE to_tsvector('english', dc.content) @@ plainto_tsquery('english', query_text)
        AND (filter_doc_type IS NULL OR (d.metadata->>'doc_type') = filter_doc_type)
    ORDER BY bm25_score DESC
    LIMIT match_count;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION bm25_search_chunks TO service_role;