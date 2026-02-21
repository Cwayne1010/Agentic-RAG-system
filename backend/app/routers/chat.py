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

    # 4. Build messages list for OpenRouter (stateless — full history each turn)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [
        {"role": m["role"], "content": m["content"]}
        for m in messages_result.data
    ]

    async def event_stream():
        full_response = []

        # 5. Stream from OpenRouter (retrieval tool enabled)
        async for event in traced_stream_chat(
            messages=messages,
            conversation_id=conversation_id,
            use_tools=True,
        ):
            if event["type"] == "delta":
                full_response.append(event["content"])
                yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"

            elif event["type"] == "tool_calls":
                for tc in event["tool_calls"]:
                    if tc["name"] == "retrieve_documents":
                        args = json.loads(tc["arguments"])
                        query = args.get("query", "")

                        # Run vector similarity search
                        chunks = await retrieval_service.search(query, str(user.id))

                        # Notify frontend that retrieval happened
                        yield f"data: {json.dumps({'type': 'retrieval', 'query': query, 'chunk_count': len(chunks)})}\n\n"

                        # Format retrieved chunks as context
                        if chunks:
                            context = "\n\n".join(
                                f"[Chunk {c['chunk_index']} | similarity {c['similarity']:.2f}]: {c['content']}"
                                for c in chunks
                            )
                        else:
                            context = "No relevant documents found in the knowledge base."

                        # Append assistant tool_calls turn + tool result to history
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": context,
                        })

                        # Re-stream with retrieved context (no tools — prevent infinite loops)
                        async for event2 in traced_stream_chat(
                            messages=messages,
                            conversation_id=conversation_id,
                            use_tools=False,
                        ):
                            if event2["type"] == "delta":
                                full_response.append(event2["content"])
                                yield f"data: {json.dumps({'type': 'delta', 'content': event2['content']})}\n\n"
                            elif event2["type"] == "done":
                                break

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
