import os
import httpx
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

EMBEDDING_MODELS = ["text-embedding-3-small", "text-embedding-3-large"]


def get_settings() -> dict:
    """Fetch the global app settings row."""
    result = supabase.table("app_settings").select("*").eq("id", 1).single().execute()
    return result.data


def has_any_documents() -> bool:
    """Check if any document chunks exist across all users."""
    result = supabase.table("document_chunks").select("id", count="exact").limit(1).execute()
    return (result.count or 0) > 0


def update_settings(embedding_model: str | None = None, chat_model: str | None = None) -> dict:
    """Update app settings. Raises ValueError if trying to change embedding model while data exists."""
    if embedding_model is not None:
        if embedding_model not in EMBEDDING_MODELS:
            raise ValueError(f"Unsupported embedding model: {embedding_model}")
        if has_any_documents():
            raise ValueError("Cannot change embedding model once documents have been ingested.")

    updates: dict = {}
    if embedding_model is not None:
        updates["embedding_model"] = embedding_model
    if chat_model is not None:
        updates["chat_model"] = chat_model

    result = supabase.table("app_settings").update(updates).eq("id", 1).execute()
    return result.data[0]


async def validate_openrouter_model(model_id: str) -> dict:
    """Check if a model ID is available on OpenRouter. Returns {valid, name}."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        models = resp.json().get("data", [])

    for m in models:
        if m.get("id") == model_id:
            return {"valid": True, "name": m.get("name", model_id)}

    return {"valid": False}
