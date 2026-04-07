# Agentic RAG System

A full-stack agentic RAG chat application — built with SvelteKit, FastAPI, Supabase, and OpenRouter. Upload documents, chat with them, and let agents decide when to search, query a database, or delegate to a sub-agent.

## Features

- **Streaming chat** with threaded conversations and tool-call display
- **Document ingestion** — drag-and-drop upload, multi-format support (PDF, DOCX, HTML, Markdown) via Docling
- **Hybrid search** — BM25 keyword + pgvector similarity with Reciprocal Rank Fusion
- **Metadata extraction** — LLM-extracted doc type, topics, and dates at ingestion time
- **Agentic tools** — web search (DuckDuckGo), text-to-SQL, and document sub-agents with isolated context
- **Record manager** — content hashing and deduplication on upload
- **Observability** — LangSmith tracing throughout
- **Per-user data isolation** — Supabase Auth + Row Level Security on every table

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | SvelteKit + TypeScript + Tailwind CSS + shadcn-svelte |
| Backend | Python + FastAPI |
| Database | Supabase (Postgres + pgvector + Auth + Storage) |
| Doc Processing | Docling |
| LLM / Embeddings | OpenRouter |
| Observability | LangSmith |

## Project Structure

```
backend/
  app/
    routers/        # chat, documents endpoints
    services/       # ingestion, retrieval, hybrid search, agents, tools
    models/         # Pydantic models
  eval/             # RAGAS evaluation suite
frontend/
  src/
    lib/components/ # Chat, document, settings UI components
    routes/         # SvelteKit pages
supabase/
  migrations/       # All database migrations
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Supabase project (with pgvector enabled)
- OpenRouter API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
uvicorn app.main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env  # fill in Supabase URL + anon key
npm run dev
```

### Database

Apply migrations in order from `supabase/migrations/` in the Supabase SQL editor.

## Evaluation

RAGAS evaluation suite lives in `backend/eval/`:

```bash
cd backend && source venv/bin/activate
python eval/run_eval.py --limit 10
```
