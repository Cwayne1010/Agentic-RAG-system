import base64
import hashlib
import os

import httpx
from cryptography.fernet import Fernet, InvalidToken
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        raw_key = os.getenv("SETTINGS_ENCRYPTION_KEY", "")
        if not raw_key:
            raise RuntimeError("SETTINGS_ENCRYPTION_KEY is not set in the environment")
        key_bytes = hashlib.sha256(raw_key.encode()).digest()
        _cipher = Fernet(base64.urlsafe_b64encode(key_bytes))
    return _cipher


def _encrypt(value: str) -> str:
    if not value:
        return ""
    return _get_cipher().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _get_cipher().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Legacy plain-text value — return as-is during migration period
        return value


def get_settings() -> dict:
    """Fetch the global app settings row with API keys decrypted."""
    result = supabase.table("app_settings").select("*").eq("id", 1).single().execute()
    data = result.data
    data["llm_api_key"] = _decrypt(data.get("llm_api_key", ""))
    data["embedding_api_key"] = _decrypt(data.get("embedding_api_key", ""))
    return data


def has_any_documents() -> bool:
    """Check if any documents exist across all users (regardless of ingestion status)."""
    try:
        result = supabase.table("documents").select("id", count="exact").limit(1).execute()
        return (result.count or 0) > 0
    except Exception:
        return False


def update_settings(
    embedding_model: str | None = None,
    chat_model: str | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_api_key: str | None = None,
    embedding_dimensions: int | None = None,
) -> dict:
    """Update app settings. Raises ValueError if trying to change embedding config while data exists."""
    current = get_settings()
    model_changing = embedding_model is not None and embedding_model != current.get("embedding_model")
    dims_changing = embedding_dimensions is not None and embedding_dimensions != current.get("embedding_dimensions", 1536)
    if (model_changing or dims_changing) and has_any_documents():
        raise ValueError("Cannot change embedding model or dimensions once documents have been ingested.")

    # Resize the DB column if the dimension is actually changing
    if dims_changing:
        supabase.rpc("resize_embedding_column", {"new_dim": embedding_dimensions}).execute()

    updates: dict = {}
    if embedding_model is not None:
        updates["embedding_model"] = embedding_model
    if chat_model is not None:
        updates["chat_model"] = chat_model
    if llm_base_url is not None:
        updates["llm_base_url"] = llm_base_url
    if llm_api_key is not None and llm_api_key != "__REDACTED__":
        updates["llm_api_key"] = _encrypt(llm_api_key)
    if embedding_base_url is not None:
        updates["embedding_base_url"] = embedding_base_url
    if embedding_api_key is not None and embedding_api_key != "__REDACTED__":
        updates["embedding_api_key"] = _encrypt(embedding_api_key)
    if embedding_dimensions is not None:
        updates["embedding_dimensions"] = embedding_dimensions

    result = supabase.table("app_settings").update(updates).eq("id", 1).execute()
    # Return decrypted keys so the response layer can mask them uniformly
    data = result.data[0]
    data["llm_api_key"] = _decrypt(data.get("llm_api_key", ""))
    data["embedding_api_key"] = _decrypt(data.get("embedding_api_key", ""))
    return data


async def validate_openrouter_model(model_id: str) -> dict:
    """Check if a model ID is available on OpenRouter. Returns {valid, name}."""
    settings = get_settings()
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
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
