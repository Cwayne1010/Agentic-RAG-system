import os
from openai import AsyncOpenAI
from app.services.settings_service import get_settings

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_LARGE_MODEL = "text-embedding-3-large"


def _embedding_kwargs(model: str) -> dict:
    """Return extra kwargs for the embeddings call (adds dimensions for large model)."""
    if model == _LARGE_MODEL:
        return {"dimensions": 1536}
    return {}


async def embed_text(text: str) -> list[float]:
    model = get_settings()["embedding_model"]
    response = await client.embeddings.create(
        model=model,
        input=text,
        **_embedding_kwargs(model),
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_settings()["embedding_model"]
    response = await client.embeddings.create(
        model=model,
        input=texts,
        **_embedding_kwargs(model),
    )
    return [d.embedding for d in response.data]
