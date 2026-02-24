-- Enable pgvector extension
create extension if not exists vector;

-- Documents table (tracks uploaded files)
create table documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  filename text not null,
  file_path text not null,
  file_size integer not null,
  mime_type text not null,
  status text not null default 'pending',   -- pending | processing | completed | failed
  error_message text,
  chunk_count integer default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Document chunks table (text + vector embeddings)
create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade not null,
  user_id uuid references auth.users(id) on delete cascade not null,
  chunk_index integer not null,
  content text not null,
  embedding vector(1536),
  token_count integer,
  created_at timestamptz default now()
);

-- RLS on documents
alter table documents enable row level security;
create policy "Users see own documents" on documents
  for all using (auth.uid() = user_id);

-- RLS on document_chunks
alter table document_chunks enable row level security;
create policy "Users see own chunks" on document_chunks
  for all using (auth.uid() = user_id);

-- Auto-update updated_at on documents
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger documents_updated_at
  before update on documents
  for each row execute function update_updated_at();

-- Realtime: enable documents table for live status updates
alter publication supabase_realtime add table documents;
alter table documents replica identity full;

-- Vector similarity search index
create index on document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- RPC function for vector similarity search
create or replace function match_document_chunks(
  query_embedding vector(1536),
  match_user_id uuid,
  match_count int default 5
)
returns table (
  id uuid,
  document_id uuid,
  content text,
  chunk_index int,
  similarity float
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) as similarity
  from document_chunks dc
  where dc.user_id = match_user_id
    and 1 - (dc.embedding <=> query_embedding) > 0.3
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
