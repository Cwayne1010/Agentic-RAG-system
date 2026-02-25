-- Migration 011: Global document corpus
--
-- Removes per-user isolation from vector search so all authenticated users
-- query across the full document corpus (shared knowledge base).

-- Drop existing RPC (signature changed — user_id param removed)
drop function if exists match_document_chunks(vector, uuid, int, text);

create or replace function match_document_chunks(
  query_embedding vector(1536),
  match_count int default 5,
  filter_doc_type text default null
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  chunk_index int,
  similarity float,
  doc_filename text,
  doc_metadata jsonb
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) as similarity,
    d.filename as doc_filename,
    d.metadata as doc_metadata
  from document_chunks dc
  join documents d on d.id = dc.document_id
  where 1 - (dc.embedding <=> query_embedding) > 0.3
    and (filter_doc_type is null or d.metadata->>'doc_type' = filter_doc_type)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
