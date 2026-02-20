-- Conversations table
create table public.conversations (
  id         uuid default gen_random_uuid() primary key,
  user_id    uuid references auth.users(id) on delete cascade not null,
  title      text not null default 'New Chat',
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null
);

alter table public.conversations enable row level security;

create policy "Users access own conversations"
  on public.conversations for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Messages table
create table public.messages (
  id              uuid default gen_random_uuid() primary key,
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  user_id         uuid references auth.users(id) on delete cascade not null,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null,
  created_at      timestamptz default now() not null
);

alter table public.messages enable row level security;

create policy "Users access own messages"
  on public.messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Auto-update updated_at on conversations
create or replace function public.update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger conversations_updated_at
  before update on public.conversations
  for each row execute procedure public.update_updated_at();

-- Bump conversation updated_at when a message is inserted
create or replace function public.touch_conversation()
returns trigger language plpgsql as $$
begin
  update public.conversations set updated_at = now() where id = new.conversation_id;
  return new;
end;
$$;

create trigger messages_touch_conversation
  after insert on public.messages
  for each row execute procedure public.touch_conversation();
