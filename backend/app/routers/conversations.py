import os
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)

router = APIRouter()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    body: ConversationCreate,
    user=Depends(get_current_user),
):
    result = (
        supabase.table("conversations")
        .insert({"user_id": str(user.id), "title": body.title})
        .execute()
    )
    return result.data[0]


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(user=Depends(get_current_user)):
    result = (
        supabase.table("conversations")
        .select("*")
        .eq("user_id", str(user.id))
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(conversation_id: str, user=Depends(get_current_user)):
    # Verify ownership
    conv = (
        supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    user=Depends(get_current_user),
):
    result = (
        supabase.table("conversations")
        .update({"title": body.title})
        .eq("id", conversation_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result.data[0]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user=Depends(get_current_user)):
    result = (
        supabase.table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
