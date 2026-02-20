import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import ChatRequest
from app.services.langsmith_service import traced_stream_response

router = APIRouter()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: ChatRequest,
    user=Depends(get_current_user),
):
    # 1. Verify conversation belongs to current user
    conv_result = (
        supabase.table("conversations")
        .select("id, title")
        .eq("id", conversation_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = conv_result.data[0]

    # 2. Insert user message
    supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "user_id": str(user.id),
        "role": "user",
        "content": body.message,
    }).execute()

    # 3. Fetch all messages for conversation
    messages_result = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    # 4. Build messages list for Claude API
    claude_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages_result.data
    ]

    async def event_stream():
        full_response = []

        # 5. Stream Claude response
        async for text in traced_stream_response(
            messages=claude_messages,
            conversation_id=conversation_id,
        ):
            full_response.append(text)
            yield f"data: {json.dumps({'type': 'delta', 'content': text})}\n\n"

        assembled = "".join(full_response)

        # 6. Insert assistant message after stream completes
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "user_id": str(user.id),
            "role": "assistant",
            "content": assembled,
        }).execute()

        # 7. Update title if still default
        if conversation["title"] == "New Chat":
            new_title = body.message[:60]
            supabase.table("conversations").update({"title": new_title}).eq(
                "id", conversation_id
            ).execute()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
