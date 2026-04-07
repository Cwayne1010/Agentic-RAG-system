import asyncio
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import ChatRequest
from app.services import document_agent_service
from app.services.chunking_service import _token_len
from app.services.langsmith_service import traced_stream_chat, start_turn_trace, end_turn_trace, record_tool_span
from app.services.openrouter_service import SYSTEM_PROMPT
from app.services.tool_executor import execute_tool

logger = logging.getLogger(__name__)

_MAX_CONTEXT_TOKENS = 100_000  # Conservative budget covering most OpenRouter models
_MAX_HISTORY_CHARS = 6_000     # ~1,500 tokens — cap each stored message in LLM context


async def _with_keepalives(source, interval: float = 10.0):
    """
    Wrap an async generator, yielding None as a keepalive marker if the source
    is silent for `interval` seconds. Allows the caller to flush SSE comments
    and prevent proxy timeouts during long LLM calls.
    """
    it = source.__aiter__()
    fut = None
    try:
        while True:
            if fut is None:
                fut = asyncio.ensure_future(it.__anext__())
            try:
                item = await asyncio.wait_for(asyncio.shield(fut), timeout=interval)
                fut = None
                yield item
            except asyncio.TimeoutError:
                yield None  # keepalive marker — caller should flush a comment
            except StopAsyncIteration:
                break
    finally:
        if fut is not None and not fut.done():
            fut.cancel()


def _trim_to_budget(messages: list[dict]) -> list[dict]:
    """Drop oldest non-system messages until total token count fits within budget."""
    while len(messages) > 2:  # Always keep system msg + at least the last user msg
        if sum(_token_len(m.get("content") or "") for m in messages) <= _MAX_CONTEXT_TOKENS:
            break
        messages.pop(1)
    return messages


def _cap_content(content: str | None) -> str | None:
    """Truncate a message's content to _MAX_HISTORY_CHARS to prevent history bloat."""
    if not content or len(content) <= _MAX_HISTORY_CHARS:
        return content
    return content[:_MAX_HISTORY_CHARS] + "\n[...truncated]"


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
        sent_done = False
        tool_calls_log: list[dict] = []  # frontend-compatible tool call state for persistence
        tool_call_offset: int | None = None  # content length when first tool call fired

        # Start root LangSmith trace for this full agentic turn
        turn_run = start_turn_trace(
            query=body.message,
            conversation_id=conversation_id,
        )

        try:
            # Module 8: Tool-calling loop — LLM decides which tools to call
            MAX_ITERATIONS = 5
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            # Cap each history message to prevent large sub-agent answers bloating context
            messages += [{"role": m["role"], "content": _cap_content(m["content"])} for m in messages_result.data]
            messages = _trim_to_budget(messages)

            for _iteration in range(MAX_ITERATIONS):
                agent_finished = False

                async for event in _with_keepalives(traced_stream_chat(
                    messages=messages,
                    conversation_id=conversation_id,
                    use_tools=True,
                    query=body.message,
                    parent_run=turn_run,
                )):
                    if event is None:
                        yield ": keepalive\n\n"
                        continue

                    if event["type"] == "delta":
                        full_response.append(event["content"])
                        yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"

                    elif event["type"] == "tool_calls":
                        tool_calls = event["tool_calls"]

                        # Record content offset on first tool call
                        if tool_call_offset is None:
                            tool_call_offset = len("".join(full_response))

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
                                sub_children: list[dict] = []
                                sub_answer = ""

                                async for sub_event in _with_keepalives(
                                    document_agent_service.run_agent(task, document_name, str(user.id))
                                ):
                                    if sub_event is None:
                                        yield ": keepalive\n\n"
                                        continue
                                    if sub_event["type"] == "tool_message":
                                        pass  # sentinel only — sub_agent_delta already captured
                                    elif sub_event["type"] == "sub_agent_delta":
                                        full_response.append(sub_event["content"])
                                        yield f"data: {json.dumps(sub_event)}\n\n"
                                    elif sub_event["type"] == "sub_agent_tool_call":
                                        sub_children.append({
                                            "tool_name": sub_event["tool_name"],
                                            "args": sub_event.get("args", {}),
                                            "status": "running",
                                        })
                                        yield f"data: {json.dumps(sub_event)}\n\n"
                                    elif sub_event["type"] == "sub_agent_tool_result":
                                        # Mark matching running child as done
                                        for child in reversed(sub_children):
                                            if child["tool_name"] == sub_event["tool_name"] and child["status"] == "running":
                                                child["status"] = "done"
                                                child["result"] = sub_event
                                                break
                                        yield f"data: {json.dumps(sub_event)}\n\n"
                                    elif sub_event["type"] == "sub_agent_done":
                                        sub_answer = sub_event.get("answer", "")
                                        yield f"data: {json.dumps(sub_event)}\n\n"
                                    else:
                                        yield f"data: {json.dumps(sub_event)}\n\n"

                                tool_calls_log.append({
                                    "tool_name": "spawn_document_agent",
                                    "args": args_parsed,
                                    "status": "done",
                                    "result": {"answer": sub_answer},
                                    "children": sub_children,
                                })
                                record_tool_span(
                                    turn_run,
                                    "spawn_document_agent",
                                    args_parsed,
                                    {"answer": sub_answer, "tool_calls": sub_children},
                                )

                                # Sub-agent answered fully — no second Sonnet synthesis needed
                                agent_finished = True
                                break  # exit for tc loop

                            else:
                                result = await execute_tool(tc["name"], tc["arguments"], str(user.id))
                                yield f"data: {json.dumps(result['sse_event'])}\n\n"
                                tool_calls_log.append({
                                    "tool_name": tc["name"],
                                    "args": args_parsed,
                                    "status": "done",
                                    "result": result["sse_event"],
                                })
                                record_tool_span(turn_run, tc["name"], args_parsed, result["sse_event"])
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result["tool_message"],
                                })

                        if agent_finished:
                            break  # exit async for event loop → triggers outer break

                    elif event["type"] == "done":
                        if not event.get("tool_calls"):
                            # Final response — no more tools
                            break
                else:
                    continue
                break  # broke out of inner for → exit outer loop too

            assembled = "".join(full_response)

            # Persist assistant message (with tool call metadata if any tools were used)
            msg_data: dict = {
                "conversation_id": conversation_id,
                "user_id": str(user.id),
                "role": "assistant",
                "content": assembled,
            }
            if tool_calls_log:
                msg_data["metadata"] = {
                    "tool_calls": tool_calls_log,
                    "tool_call_offset": tool_call_offset or 0,
                }
            supabase.table("messages").insert(msg_data).execute()

            # Auto-title conversation from first message
            if conversation["title"] == "New Chat":
                new_title = body.message[:60]
                supabase.table("conversations").update({"title": new_title}).eq(
                    "id", conversation_id
                ).execute()

            end_turn_trace(turn_run, "".join(full_response))
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            sent_done = True

        except Exception:
            logger.exception("event_stream error — sending done to unblock client")
            end_turn_trace(turn_run, "".join(full_response))

        if not sent_done:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
