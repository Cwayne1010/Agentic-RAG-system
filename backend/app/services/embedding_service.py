import os
from openai import AsyncOpenAI
from app.services.settings_service import get_settings


def _get_embedding_client(settings: dict) -> AsyncOpenAI:
    api_key = settings.get("embedding_api_key") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = settings.get("embedding_base_url") or "https://openrouter.ai/api/v1"
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _supports_dimensions(model: str) -> bool:
    """Only OpenAI text-embedding-3 models support the dimensions parameter."""
    return "text-embedding-3" in model


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    client = _get_embedding_client(settings)
    model = settings["embedding_model"]
    dimensions = settings.get("embedding_dimensions") or 0

    kwargs: dict = {"model": model, "input": text}
    if dimensions > 0 and _supports_dimensions(model):
        kwargs["dimensions"] = dimensions

    response = await client.embeddings.create(**kwargs)
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    client = _get_embedding_client(settings)
    model = settings["embedding_model"]
    dimensions = settings.get("embedding_dimensions") or 0

    kwargs: dict = {"model": model, "input": texts}
    if dimensions > 0 and _supports_dimensions(model):
        kwargs["dimensions"] = dimensions

    response = await client.embeddings.create(**kwargs)
    return [d.embedding for d in response.data]
