from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(override=True)

from app.routers import conversations, chat, documents, settings, metrics  # noqa: E402

app = FastAPI(title="Agentic RAG Masterclass API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "https://agentic-rag-system-6t1u6ztod-caden-waynes-projects.vercel.app", "https://agentic-rag-system-two.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/keys")
async def debug_keys():
    import os
    from app.services.settings_service import get_settings
    settings = get_settings()
    embedding_key = settings.get("embedding_api_key", "")
    llm_key = settings.get("llm_api_key", "")
    env_key = os.getenv("OPENROUTER_API_KEY", "")
    return {
        "embedding_key_len": len(embedding_key),
        "embedding_key_prefix": embedding_key[:8] if embedding_key else None,
        "llm_key_len": len(llm_key),
        "llm_key_prefix": llm_key[:8] if llm_key else None,
        "env_key_len": len(env_key),
        "env_key_prefix": env_key[:8] if env_key else None,
    }
