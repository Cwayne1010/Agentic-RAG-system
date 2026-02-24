from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import get_current_user
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
    embedding_locked: bool
    llm_base_url: str
    llm_api_key: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_dimensions: int


class SettingsPatch(BaseModel):
    embedding_model: str | None = None
    chat_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_dimensions: int | None = None


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
        embedding_locked=locked,
        llm_base_url=settings.get("llm_base_url", "https://openrouter.ai/api/v1"),
        llm_api_key=_mask(settings.get("llm_api_key", "")),
        embedding_base_url=settings.get("embedding_base_url", "https://openrouter.ai/api/v1"),
        embedding_api_key=_mask(settings.get("embedding_api_key", "")),
        embedding_dimensions=settings.get("embedding_dimensions", 1536),
    )


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(body: SettingsPatch, _user=Depends(get_current_user)):
    try:
        updated = update_settings(
            embedding_model=body.embedding_model,
            chat_model=body.chat_model,
            llm_base_url=body.llm_base_url,
            llm_api_key=body.llm_api_key,
            embedding_base_url=body.embedding_base_url,
            embedding_api_key=body.embedding_api_key,
            embedding_dimensions=body.embedding_dimensions,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    locked = has_any_documents()
    return SettingsResponse(
        embedding_model=updated["embedding_model"],
        chat_model=updated["chat_model"],
        embedding_locked=locked,
        llm_base_url=updated.get("llm_base_url", "https://openrouter.ai/api/v1"),
        llm_api_key=_mask(updated.get("llm_api_key", "")),
        embedding_base_url=updated.get("embedding_base_url", "https://openrouter.ai/api/v1"),
        embedding_api_key=_mask(updated.get("embedding_api_key", "")),
        embedding_dimensions=updated.get("embedding_dimensions", 1536),
    )


@router.post("/settings/validate-model", response_model=ValidateModelResponse)
async def validate_model(body: ValidateModelRequest, _user=Depends(get_current_user)):
    try:
        result = await validate_openrouter_model(body.model_id)
        return ValidateModelResponse(**result)
    except Exception as e:
        raise HTTPException(502, detail=f"Failed to reach OpenRouter: {e}")
