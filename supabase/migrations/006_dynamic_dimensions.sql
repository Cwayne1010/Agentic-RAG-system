-- Allow match_document_chunks to accept any vector dimension
-- (removes the hard-coded vector(1536) on the parameter)
DROP FUNCTION IF EXISTS match_document_chunks(vector, uuid, integer);
CREATE OR REPLACE FUNCTION match_document_chunks(
  query_embedding vector,
  match_user_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id          uuid,
  document_id uuid,
  content     text,
  chunk_index int,
  similarity  float
)
LANGUAGE sql STABLE AS $$
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) AS similarity
  FROM document_chunks dc
  WHERE dc.user_id = match_user_id
    AND 1 - (dc.embedding <=> query_embedding) > 0.3
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Resize the embedding column and index to a new dimension.
-- Called by the backend when embedding_dimensions changes and no documents exist.
CREATE OR REPLACE FUNCTION resize_embedding_column(new_dim INT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  DROP INDEX IF EXISTS document_chunks_embedding_idx;
  EXECUTE format(
    'ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(%s)',
    new_dim
  );
  EXECUTE format(
    'CREATE INDEX document_chunks_embedding_idx ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
  );
END;
$$;
