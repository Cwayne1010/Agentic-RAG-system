import asyncio
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import ChatRequest
from app.services import retrieval_service, document_agent_service
from app.services.chunking_service import _token_len
from app.services.langsmith_service import traced_stream_chat
from app.services.openrouter_service import SYSTEM_PROMPT
from app.services.tool_executor import execute_tool

_MAX_CONTEXT_TOKENS = 100_000  # Conservative budget covering most OpenRouter models



def _trim_to_budget(messages: list[dict]) -> list[dict]:
    """Drop oldest non-system messages until total token count fits within budget."""
    while len(messages) > 2:  # Always keep system msg + at least the last user msg
        if sum(_token_len(m["content"]) for m in messages) <= _MAX_CONTEXT_TOKENS:
            break
        messages.pop(1)
    return messages


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

        # Module 8: Tool-calling loop — LLM decides which tools to call
        MAX_ITERATIONS = 5
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": m["role"], "content": m["content"]} for m in messages_result.data]
        messages = _trim_to_budget(messages)

        for _iteration in range(MAX_ITERATIONS):
            async for event in traced_stream_chat(
                messages=messages,
                conversation_id=conversation_id,
                use_tools=True,
                query=body.message,
            ):
                if event["type"] == "delta":
                    full_response.append(event["content"])
                    yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"

                elif event["type"] == "tool_calls":
                    tool_calls = event["tool_calls"]

                    # Append LLM's tool_calls to message history
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]},
                            }
                            for tc in tool_calls
                        ],
                    })

                    for tc in tool_calls:
                        try:
                            args_parsed = json.loads(tc["arguments"])
                        except json.JSONDecodeError:
                            args_parsed = {}

                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': tc['name'], 'args': args_parsed})}\n\n"

                        if tc["name"] == "spawn_document_agent":
                            task = args_parsed.get("task", "")
                            document_name = args_parsed.get("document_name")
                            tool_message_content = ""

                            async for sub_event in document_agent_service.run_agent(task, document_name, str(user.id)):
                                if sub_event["type"] == "tool_message":
                                    tool_message_content = sub_event["content"]
                                else:
                                    yield f"data: {json.dumps(sub_event)}\n\n"

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": tool_message_content or "Sub-agent returned no result.",
                            })
                        else:
                            result = await execute_tool(tc["name"], tc["arguments"], str(user.id))
                            yield f"data: {json.dumps(result['sse_event'])}\n\n"
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": result["tool_message"],
                            })

                elif event["type"] == "done":
                    if not event.get("tool_calls"):
                        # Final response — no more tools
                        break
            else:
                continue
            break  # broke out of inner for → exit outer loop too

        assembled = "".join(full_response)

        # Persist assistant message
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "user_id": str(user.id),
            "role": "assistant",
            "content": assembled,
        }).execute()

        # Auto-title conversation from first message
        if conversation["title"] == "New Chat":
            new_title = body.message[:60]
            supabase.table("conversations").update({"title": new_title}).eq(
                "id", conversation_id
            ).execute()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
