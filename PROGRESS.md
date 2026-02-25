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

### Module 2: BYO Retrieval + Memory

- [x] Phase 1: DB schema (documents + document_chunks + pgvector RPC) + Supabase Storage bucket
- [x] Phase 2: LLM switch — Claude → OpenRouter (openrouter_service.py, updated chat.py, langsmith_service.py, deleted claude_service.py, installed openai + python-multipart)
- [x] Phase 3: Document ingestion backend (embedding_service.py, chunking_service.py, ingestion_service.py, models/document.py, routers/documents.py, main.py updated)
- [x] Phase 4: Retrieval tool + RAG chat integration (retrieval_service.py + chat.py tool-call loop)
- [x] Phase 5: Frontend ingestion UI (documents route, FileUploadZone, DocumentList, Supabase Realtime, nav)

### Validation Suite (Modules 1 & 2)

- [x] Automated test runner created (`backend/run_validation.py`)
- [x] 23/27 automated tests passing
- [x] 004 migration applied (8 SQL template RPCs created in Supabase)
- [x] Validation document: `Tickler_System_Executive_Summary.md` (uploaded, 37 chunks)

**Automated results (last run):**
- PASS: P1, P3, A3, C1–C5, CH4, CH5, V1, V3, V4, D2, D3, D4, S1–S4, I1, I2, SQL2, SQL3, SQL4, RM1, RM3–RM7 (31/31)
- SKIP (manual): I3 (SQL editor), SQL1 (SQL editor), RM2 (SQL editor — migration confirmed applied)
- MANUAL (not yet run): P2, A1, A2, A4, CH1, CH2, CH3, D1, D4(browser), D5, D6, V2, L1, V5, S5, UX1–UX4
- BROWSER COMPLETE: RM8 (duplicate warning toast), RM9 (update toast + stale card replaced)
- COMPLETE: R1–R3 (RAGAS eval framework — golden set generated, eval runs with --limit and --metrics flags)

### Module 3: Record Manager

- [x] Task 1: Apply migration 008_content_hash.sql (content_hash column + partial unique index)
- [x] Task 2: Model — add content_hash field to DocumentResponse
- [x] Task 3: Router — hash computation, dedup check (409), same-filename cleanup, store hash
- [x] Task 4: Frontend api.ts — parse JSON error body for clean detail message
- [x] Task 5: Frontend documents page — warning toast for duplicates, update toast + stale entry removal
- [x] Task 6: Validation — RM1–RM9 added to validation suite

**Key discoveries during validation:**
- RPC `match_document_chunks` uses `match_user_id` param (not `p_user_id`), no `match_threshold` (hardcoded 0.3)
- `supabase-py` `auth.sign_in_with_password()` replaces the service-role token — use REST API for tokens instead
- 004 migration needed `SET transaction_read_only = on` removed (not supported in Supabase Postgres)

### Module 4: Metadata Extraction

- [ ] Task 1: Apply migration 009_document_metadata.sql (metadata JSONB column + updated RPC with JOIN + filter_doc_type)
- [x] Task 2: Create metadata_service.py (DocumentMetadata Pydantic model + extract_metadata LLM call)
- [x] Task 3: Update ingestion_service.py — call extract_metadata after chunks embedded, store in documents.metadata
- [x] Task 4: Update retrieval_service.py — add doc_type_filter param, pass to RPC when set
- [x] Task 5: Update chat.py — enrich context block with source metadata; add sources list to retrieval SSE event
- [x] Task 6: Update models/document.py — add metadata field to DocumentResponse
- [x] Task 7: Frontend types/index.ts + DocumentList.svelte — add DocumentMetadata type, show doc_type badge + topic chips
- [x] Task 8: Frontend api.ts + +page.svelte — onRetrieval callback, toast with chunk count and source filenames
- [x] Task 9: Validation — M4-1 through M4-5 (backend) and M4-UX1/M4-UX2 (frontend) added to validation suite

### Module 5: Multi-Format Support

- [x] Task 1: Install docling (pip install docling + requirements.txt updated)
- [x] Task 2: Create parsing_service.py (bytes → text; docling for PDF/DOCX/HTML, UTF-8 decode for TXT/MD)
- [x] Task 3: Update documents.py router (expanded MIME types, asyncio.to_thread parse, typed error handling)
- [x] Task 4: Update FileUploadZone.svelte (accept new types in drop filter + input, updated help text)
- [x] Task 5: Validation — M5-1 through M5-5 (backend) and M5-UX1/M5-UX2 (frontend) added to validation suite

### Module 6: Hybrid Search & Reranking

- [x] Task 1: Create migration 013_hybrid_search.sql (GIN index + bm25_search_chunks RPC function)
- [x] Task 2: Create hybrid_search_service.py (BM25 + vector search with Reciprocal Rank Fusion)
- [x] Task 3: Update retrieval_service.py (hybrid search by default, search_mode parameter for vector/hybrid)
- [x] Task 4: Validation — M6-1 through M6-5 (migration, RPC, hybrid search, comparison, search modes)
