import json
import os

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.services.metadata_service import _TOPIC_VOCABULARY as _FALLBACK_VOCABULARY
from app.services.settings_service import (
    get_settings,
    has_any_documents,
    update_settings,
    validate_openrouter_model,
)

router = APIRouter()


class SettingsResponse(BaseModel):
    embedding_model: str
    chat_model: str
    map_model: str
    embedding_locked: bool
    llm_base_url: str
    llm_api_key: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_dimensions: int
    business_description: str
    topic_vocabulary: list[str]
    metadata_schema: list[dict]


class SettingsPatch(BaseModel):
    embedding_model: str | None = None
    chat_model: str | None = None
    map_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_dimensions: int | None = None
    business_description: str | None = None
    topic_vocabulary: list[str] | None = None
    metadata_schema: list[dict] | None = None


class GenerateVocabularyRequest(BaseModel):
    business_description: str


class GenerateVocabularyResponse(BaseModel):
    vocabulary: list[str]


class ValidateModelRequest(BaseModel):
    model_id: str


class ValidateModelResponse(BaseModel):
    valid: bool
    name: str | None = None


def _mask(key: str) -> str:
    """Return a sentinel when a key is set so the actual value is never exposed."""
    return "__REDACTED__" if key else ""


@router.get("/settings", response_model=SettingsResponse)
async def read_settings(_user=Depends(get_current_user)):
    settings = get_settings()
    locked = has_any_documents()
    return SettingsResponse(
        embedding_model=settings["embedding_model"],
        chat_model=settings["chat_model"],
        map_model=settings.get("map_model", "google/gemini-1.5-flash"),
        embedding_locked=locked,
        llm_base_url=settings.get("llm_base_url", "https://openrouter.ai/api/v1"),
        llm_api_key=_mask(settings.get("llm_api_key", "")),
        embedding_base_url=settings.get("embedding_base_url", "https://openrouter.ai/api/v1"),
        embedding_api_key=_mask(settings.get("embedding_api_key", "")),
        embedding_dimensions=settings.get("embedding_dimensions", 1536),
        business_description=settings.get("business_description", ""),
        topic_vocabulary=settings.get("topic_vocabulary") or [],
        metadata_schema=settings.get("metadata_schema") or [],
    )


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(body: SettingsPatch, _user=Depends(get_current_user)):
    try:
        updated = update_settings(
            embedding_model=body.embedding_model,
            chat_model=body.chat_model,
            map_model=body.map_model,
            llm_base_url=body.llm_base_url,
            llm_api_key=body.llm_api_key,
            embedding_base_url=body.embedding_base_url,
            embedding_api_key=body.embedding_api_key,
            embedding_dimensions=body.embedding_dimensions,
            business_description=body.business_description,
            topic_vocabulary=body.topic_vocabulary,
            metadata_schema=body.metadata_schema,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    locked = has_any_documents()
    return SettingsResponse(
        embedding_model=updated["embedding_model"],
        chat_model=updated["chat_model"],
        map_model=updated.get("map_model", "google/gemini-1.5-flash"),
        embedding_locked=locked,
        llm_base_url=updated.get("llm_base_url", "https://openrouter.ai/api/v1"),
        llm_api_key=_mask(updated.get("llm_api_key", "")),
        embedding_base_url=updated.get("embedding_base_url", "https://openrouter.ai/api/v1"),
        embedding_api_key=_mask(updated.get("embedding_api_key", "")),
        embedding_dimensions=updated.get("embedding_dimensions", 1536),
        business_description=updated.get("business_description", ""),
        topic_vocabulary=updated.get("topic_vocabulary") or [],
        metadata_schema=updated.get("metadata_schema") or [],
    )


@router.post("/settings/generate-vocabulary", response_model=GenerateVocabularyResponse)
async def generate_vocabulary(body: GenerateVocabularyRequest, _user=Depends(get_current_user)):
    if not body.business_description.strip():
        raise HTTPException(400, detail="business_description is required")

    settings = get_settings()
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    base_url = settings.get("llm_base_url") or "https://openrouter.ai/api/v1"
    model = settings["chat_model"]

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    prompt = (
        "You are a knowledge architect. Given a business description, produce a short list of broad topic tags "
        "that cover the most important subject areas relevant to documents this business would work with.\n\n"
        "Rules:\n"
        "- Return ONLY a JSON array of strings, no other text\n"
        "- Tags must be lowercase kebab-case (e.g. 'fleet-management', 'client-onboarding')\n"
        "- Aim for exactly 10 tags — broad and high-level, not granular\n"
        "- Each tag should cover a wide swath of related documents, not a narrow topic\n\n"
        f"Business description:\n{body.business_description}"
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={"HTTP-Referer": "http://localhost:5173"},
        )
        raw = response.choices[0].message.content or "[]"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        vocabulary = json.loads(raw)
        if not isinstance(vocabulary, list):
            raise ValueError("Expected a JSON array")
        vocabulary = [t for t in vocabulary if isinstance(t, str) and t]
        # Merge with fallback so universal terms are always present
        vocabulary = list(dict.fromkeys(vocabulary + _FALLBACK_VOCABULARY))
    except Exception as e:
        raise HTTPException(502, detail=f"Vocabulary generation failed: {e}")

    update_settings(
        business_description=body.business_description,
        topic_vocabulary=vocabulary,
    )
    return GenerateVocabularyResponse(vocabulary=vocabulary)


@router.post("/settings/validate-model", response_model=ValidateModelResponse)
async def validate_model(body: ValidateModelRequest, _user=Depends(get_current_user)):
    try:
        result = await validate_openrouter_model(body.model_id)
        return ValidateModelResponse(**result)
    except Exception as e:
        raise HTTPException(502, detail=f"Failed to reach OpenRouter: {e}")
