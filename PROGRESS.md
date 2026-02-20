# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability

**Stack note:** Frontend uses SvelteKit + shadcn-svelte + Tailwind CSS v4 

- [x] Task 1: Backend project setup (venv, FastAPI, CORS, /health)
- [x] Task 2: Supabase database schema (conversations + messages with RLS)
- [x] Task 3: Backend auth dependency (JWT validation via Supabase)
- [x] Task 4: Pydantic models (ConversationCreate, ChatRequest, etc.)
- [x] Task 5: Conversations router (CRUD endpoints)
- [x] Task 6: Claude API service (streaming via AsyncAnthropic)
- [x] Task 7: LangSmith tracing service (@traceable decorator)
- [x] Task 8: Chat SSE endpoint (streaming response + message persistence)
- [x] Task 9: Frontend setup (SvelteKit + shadcn-svelte + Tailwind v4 + Vite proxy)
- [x] Task 10: Supabase client + API helpers (apiRequest, streamChat)
- [x] Task 11: Auth gating (+layout.svelte checks session, shows AuthForm)
- [x] Task 12: Chat layout + sidebar (ChatSidebar, MessageList, MessageBubble, MessageInput)
- [x] Task 13: Streaming wired up in +page.svelte (optimistic UI + SSE)

## Before Running

1. Run `supabase/migrations/001_schema.sql` in the Supabase SQL editor
2. Copy `backend/.env.example` → `backend/.env` and fill in credentials
3. Copy `frontend/.env.example` → `frontend/.env` and fill in Supabase URL + anon key
4. Start backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
5. Start frontend: `cd frontend && npm run dev`

### Module 2: Document Ingestion
- [ ] Not started
