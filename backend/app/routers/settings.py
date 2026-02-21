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


class SettingsPatch(BaseModel):
    embedding_model: str | None = None
    chat_model: str | None = None


class ValidateModelRequest(BaseModel):
    model_id: str


class ValidateModelResponse(BaseModel):
    valid: bool
    name: str | None = None


@router.get("/settings", response_model=SettingsResponse)
async def read_settings(_user=Depends(get_current_user)):
    settings = get_settings()
    locked = has_any_documents()
    return SettingsResponse(
        embedding_model=settings["embedding_model"],
        chat_model=settings["chat_model"],
        embedding_locked=locked,
    )


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(body: SettingsPatch, _user=Depends(get_current_user)):
    try:
        updated = update_settings(
            embedding_model=body.embedding_model,
            chat_model=body.chat_model,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    locked = has_any_documents()
    return SettingsResponse(
        embedding_model=updated["embedding_model"],
        chat_model=updated["chat_model"],
        embedding_locked=locked,
    )


@router.post("/settings/validate-model", response_model=ValidateModelResponse)
async def validate_model(body: ValidateModelRequest, _user=Depends(get_current_user)):
    try:
        result = await validate_openrouter_model(body.model_id)
        return ValidateModelResponse(**result)
    except Exception as e:
        raise HTTPException(502, detail=f"Failed to reach OpenRouter: {e}")
