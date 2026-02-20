# Module 1: App Shell + Observability

⚠️ **Medium** — Multiple components (auth, chat UI, backend API, Claude API, LangSmith) but well-scoped and greenfield.

## Context

This is the foundation module. We build the complete app shell: Supabase authentication, a threaded chat UI, and an integration with Anthropic's Claude API for streaming chat responses. LangSmith tracing is added from day one.

Claude's Messages API is stateless — we store conversation history in the database and send the full message thread on each request. This keeps the architecture transparent and educational (no black-box thread management). Everything built here — auth, routing, UI shell, SSE streaming, message storage — carries forward into all subsequent modules.

## Prerequisites (must be done manually before build)

- Supabase project created → have URL, anon key, service role key
- Anthropic API key
- LangSmith account, API key, and project name

## Directory Structure

```
frontend/
  src/
    components/
      ui/                    # shadcn/ui auto-generated
      chat/
        ChatSidebar.tsx
        MessageList.tsx
        MessageBubble.tsx
        MessageInput.tsx
      auth/
        AuthForm.tsx
    pages/
      AuthPage.tsx
      ChatPage.tsx
    lib/
      supabase.ts            # Supabase browser client
      api.ts                 # Fetch wrapper + SSE helper
    types/
      index.ts               # Shared TypeScript types
    App.tsx
    main.tsx
  package.json
  .env.example

backend/
  app/
    __init__.py
    main.py                  # FastAPI app + CORS
    dependencies.py          # get_current_user auth dependency
    routers/
      __init__.py
      conversations.py       # Conversation CRUD endpoints
      chat.py                # SSE streaming endpoint
    services/
      __init__.py
      claude_service.py      # Anthropic Messages API integration
      langsmith_service.py   # Tracing wrapper
    models/
      __init__.py
      conversation.py        # Pydantic request/response models
  requirements.txt
  .env.example

supabase/
  migrations/
    001_schema.sql
```

---

## Tasks

### Task 1: Backend Project Setup

1. Create `backend/` directory with `app/` package structure (add `__init__.py` files)
2. Create venv: `python3 -m venv backend/venv`
3. Create `backend/requirements.txt`:
   ```
   fastapi
   uvicorn[standard]
   python-dotenv
   supabase
   anthropic
   langsmith
   pydantic
   httpx
   ```
4. Install: `source backend/venv/bin/activate && pip install -r backend/requirements.txt`
5. Create `backend/.env.example`:
   ```
   SUPABASE_URL=
   SUPABASE_SERVICE_ROLE_KEY=
   ANTHROPIC_API_KEY=
   CLAUDE_MODEL=claude-sonnet-4-6
   LANGSMITH_API_KEY=
   LANGSMITH_PROJECT=agentic-rag-masterclass
   LANGCHAIN_TRACING_V2=true
   ```
6. Create `backend/app/main.py`:
   - FastAPI app with CORS allowing `http://localhost:5173`
   - Mount routers under `/api`
   - `GET /health` returns `{"status": "ok"}`
   - Load `.env` via `python-dotenv`

**Validation:** `uvicorn app.main:app --reload` (from `backend/`) starts without errors. `GET /health` → 200.

---

### Task 2: Supabase Database Schema

Create `supabase/migrations/001_schema.sql` and run in Supabase SQL editor:

```sql
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
```

**Validation:** Both tables visible in Supabase dashboard with RLS enabled and policies listed.

---

### Task 3: Backend Auth Dependency

Create `backend/app/dependencies.py`:
- Extract Bearer token from `Authorization` header
- Validate via Supabase service-role client `auth.get_user(token)`
- Return user object or raise `HTTPException(401)`

```python
from fastapi import Header, HTTPException
from supabase import create_client
import os

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

async def get_current_user(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = supabase.auth.get_user(token)
        return result.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Validation:** Protected route returns 401 without token, 200 with valid Supabase JWT.

---

### Task 4: Pydantic Models

Create `backend/app/models/conversation.py`:

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ConversationCreate(BaseModel):
    title: str = "New Chat"

class ConversationUpdate(BaseModel):
    title: str

class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

class ChatRequest(BaseModel):
    message: str
```

---

### Task 5: Conversations Router

Create `backend/app/routers/conversations.py`:

- `POST /api/conversations` — insert row, return `ConversationResponse`
- `GET /api/conversations` — list user's conversations ordered by `updated_at desc`
- `GET /api/conversations/{id}/messages` — fetch all messages for a conversation (verify ownership)
- `PATCH /api/conversations/{id}` — update title (verify ownership)
- `DELETE /api/conversations/{id}` — delete conversation and its messages (cascade)

All endpoints inject `get_current_user`.

**Validation:** Full CRUD via curl with a valid Supabase JWT token. Messages endpoint returns ordered list.

---

### Task 6: Claude API Service

Create `backend/app/services/claude_service.py`:

```python
import os
from anthropic import AsyncAnthropic
from typing import AsyncGenerator

client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

async def stream_response(
    messages: list[dict],   # [{"role": "user"|"assistant", "content": "..."}]
    system_prompt: str = "You are a helpful AI assistant.",
) -> AsyncGenerator[str, None]:
    """
    Streams text from Claude given the full conversation history.
    Claude's API is stateless — caller provides complete message history each turn.
    """
    async with client.messages.stream(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

**Validation:** Direct async test call streams content from Claude without error.

---

### Task 7: LangSmith Tracing Service

Create `backend/app/services/langsmith_service.py`:

```python
from langsmith import traceable
from .claude_service import stream_response
from typing import AsyncGenerator

@traceable(name="module1_chat", run_type="llm")
async def traced_stream_response(
    messages: list[dict],
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    return stream_response(messages)
```

LangSmith auto-captures inputs and outputs via the `@traceable` decorator.
Configured via env: `LANGCHAIN_TRACING_V2=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

**Validation:** After a chat call, trace appears in LangSmith dashboard under the configured project.

---

### Task 8: Chat SSE Endpoint

Create `backend/app/routers/chat.py`:

- `POST /api/conversations/{id}/messages` → `StreamingResponse` with `media_type="text/event-stream"`
- Steps:
  1. Verify conversation belongs to current user
  2. Insert user message into `messages` table
  3. Fetch all messages for conversation (ordered by `created_at asc`)
  4. Build `messages` list for Claude API: `[{"role": m.role, "content": m.content}]`
  5. Stream Claude response, emitting SSE events:
     ```
     data: {"type": "delta", "content": "Hello"}

     data: {"type": "done"}

     ```
  6. After stream completes: insert assistant message into `messages` table
  7. If conversation title is still "New Chat": update title to first 60 chars of user message

**Validation:** `curl -N -X POST` with valid token shows streaming chunks. Both user and assistant messages appear in the `messages` table after the call.

---

### Task 9: Frontend Project Setup *(SvelteKit — not React)*

```bash
npx sv create frontend --template minimal --types ts --no-add-ons --no-install --no-dir-check
cd frontend && npm install
npm install -D tailwindcss postcss autoprefixer @tailwindcss/vite
npx shadcn-svelte@latest init --base-color zinc --css src/app.css \
  --components-alias '$lib/components' --lib-alias '$lib' \
  --utils-alias '$lib/utils' --hooks-alias '$lib/hooks' --ui-alias '$lib/components/ui'
npx shadcn-svelte@latest add button input textarea scroll-area separator avatar sonner --yes
npm install @supabase/supabase-js marked
```

`vite.config.ts` — add `@tailwindcss/vite` plugin + proxy for FastAPI:
```typescript
server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } }
```

Create `frontend/.env.example` (PUBLIC_ prefix = SvelteKit convention):
```
PUBLIC_SUPABASE_URL=
PUBLIC_SUPABASE_ANON_KEY=
```
No API URL needed — Vite proxy routes `/api/...` to FastAPI automatically.

**Validation:** `npm run dev` starts on `localhost:5173` without errors.

---

### Task 10: Supabase Client + API Helper

`frontend/src/lib/supabase.ts` — `createClient` from `$env/static/public`.

`frontend/src/lib/api.ts`:
- `apiRequest(path, options)` — attaches `Authorization: Bearer <token>`; calls relative `/api/...` path
- `streamChat(conversationId, message, onDelta, onDone, onError)` — SSE via fetch ReadableStream

`frontend/src/types/index.ts` — `Conversation`, `Message` interfaces (unchanged from plan).

`frontend/src/lib/stores/conversations.ts` — writable stores:
- `conversations`, `activeConversationId`, `messages`, `isStreaming`

---

### Task 11: Auth Gating

`frontend/src/routes/+layout.ts` — `export const ssr = false` (pure SPA).

`frontend/src/routes/+layout.svelte`:
- Imports `../app.css`, `<Toaster>` from shadcn-svelte Sonner
- `onMount`: subscribes to `supabase.auth.onAuthStateChange`
- If session → `{@render children()}`, else → `<AuthForm />`

`frontend/src/lib/components/auth/AuthForm.svelte`:
- Svelte 5 runes (`$state`) for mode/email/password/error/loading
- shadcn-svelte `<Input>` and `<Button>`
- Tab toggle Login / Sign Up

---

### Task 12: Chat Layout + Sidebar

`frontend/src/routes/+page.svelte` — two-column layout (sidebar 240px + main flex-1).

`ChatSidebar.svelte` — loads conversations on mount; selects conversation + loads messages into store; New Chat; Logout. Exports `refresh()` method for title reloads.

`MessageList.svelte` — shadcn-svelte `<ScrollArea>`; `$effect` auto-scrolls on `$messages` change.

`MessageBubble.svelte` — user right-aligned; assistant left-aligned with `{@html marked(content)}`; blinking cursor when `message.streaming`.

`MessageInput.svelte` — `<Textarea>` with Enter-to-send; disabled while `$isStreaming`.

---

### Task 13: Wire Up Streaming

In `+page.svelte` `handleSend()`:
1. Optimistic user message → messages store
2. Placeholder assistant message with `streaming: true`
3. `isStreaming.set(true)` → `streamChat(...)` with delta/done/error callbacks
4. `onDone`: set `streaming: false`, call `sidebarRef.refresh()` for title update
5. `onError`: remove placeholder, `toast.error()`, re-enable input

---

### Task 14: Update PROGRESS.md *(done)*

---

## Environment Variables Summary

**`backend/.env`** (copy from `.env.example`, fill in values):
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=agentic-rag-masterclass
LANGCHAIN_TRACING_V2=true
```

**`frontend/.env`** (copy from `.env.example`, fill in values):
```
PUBLIC_SUPABASE_URL=https://xxx.supabase.co
PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

---

## End-to-End Validation

1. Run SQL migration in Supabase SQL editor → both tables appear with RLS enabled
2. `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
3. `cd frontend && npm run dev`
4. Open `http://localhost:5173`
5. Sign up for a new account → redirected to chat
6. Click "New Chat", type a message, press Enter
7. Verify response streams token by token
8. Refresh page → conversation appears in sidebar, messages load on click
9. Open LangSmith → trace appears under project `agentic-rag-masterclass`
10. Open Supabase table editor → `messages` table has both user and assistant rows
