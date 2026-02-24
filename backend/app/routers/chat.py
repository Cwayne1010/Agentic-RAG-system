import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import ChatRequest
from app.services.langsmith_service import traced_stream_chat
from app.services import retrieval_service
from app.services.openrouter_service import SYSTEM_PROMPT

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

    # 3. Fetch full conversation history
    messages_result = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    async def event_stream():
        full_response = []

        # 4. Pre-fetch retrieval using the user message directly — runs before any LLM call.
        #    Reduces 2 sequential LLM calls to 1 by injecting context upfront.
        chunks = await retrieval_service.search(body.message, str(user.id))

        # Notify frontend (chunk_count: 0 means no docs matched — LLM will use general knowledge)
        yield f"data: {json.dumps({'type': 'retrieval', 'query': body.message, 'chunk_count': len(chunks)})}\n\n"

        # Build context block if chunks were found
        context_block = ""
        if chunks:
            context_lines = "\n\n".join(
                f"[Chunk {c['chunk_index']} | similarity {c['similarity']:.2f}]: {c['content']}"
                for c in chunks
            )
            context_block = f"\n\n<retrieved_context>\n{context_lines}\n</retrieved_context>"

        # 5. Build messages list — context injected into system message
        messages = [{"role": "system", "content": SYSTEM_PROMPT + context_block}]
        messages += [
            {"role": m["role"], "content": m["content"]}
            for m in messages_result.data
        ]

        # 6. Single LLM call — no tools needed, context is already in system message
        async for event in traced_stream_chat(
            messages=messages,
            conversation_id=conversation_id,
            use_tools=False,
        ):
            if event["type"] == "delta":
                full_response.append(event["content"])
                yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"
            elif event["type"] == "done":
                break

        assembled = "".join(full_response)

        # 6. Persist assistant message
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "user_id": str(user.id),
            "role": "assistant",
            "content": assembled,
        }).execute()

        # 7. Auto-title conversation from first message
        if conversation["title"] == "New Chat":
            new_title = body.message[:60]
            supabase.table("conversations").update({"title": new_title}).eq(
                "id", conversation_id
            ).execute()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
