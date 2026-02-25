-- Add metadata JSONB column to documents
alter table documents add column if not exists metadata jsonb;

-- Drop existing RPC and recreate with document metadata JOIN + optional doc_type filter
drop function if exists match_document_chunks(vector, uuid, int);

create or replace function match_document_chunks(
  query_embedding vector(1536),
  match_user_id uuid,
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
  where dc.user_id = match_user_id
    and 1 - (dc.embedding <=> query_embedding) > 0.3
    and (filter_doc_type is null or d.metadata->>'doc_type' = filter_doc_type)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
