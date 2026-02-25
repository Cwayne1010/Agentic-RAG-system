import asyncio
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

from app.dependencies import get_current_user
from app.models.conversation import ChatRequest
from app.services import retrieval_service
from app.services.chunking_service import _token_len
from app.services.langsmith_service import traced_stream_chat
from app.services.openrouter_service import SYSTEM_PROMPT, structured_chat

_MAX_CONTEXT_TOKENS = 100_000  # Conservative budget covering most OpenRouter models


class DocumentMapResult(BaseModel):
    document_name: str
    key_points: list[str]
    relevant: bool


def _trim_to_budget(messages: list[dict]) -> list[dict]:
    """Drop oldest non-system messages until total token count fits within budget."""
    while len(messages) > 2:  # Always keep system msg + at least the last user msg
        if sum(_token_len(m["content"]) for m in messages) <= _MAX_CONTEXT_TOKENS:
            break
        messages.pop(1)
    return messages


router = APIRouter()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def _full_context_events(question: str, history_data: list[dict], conversation_id: str):
    """Async generator for map-reduce full context mode.

    Yields dicts matching the traced_stream_chat event shape, plus an initial
    retrieval event: {"type": "retrieval", "chunk_count": int, "sources": list, "doc_count": int}
    """
    chunks_by_doc = await retrieval_service.fetch_all_chunks_by_document()
    doc_count = len(chunks_by_doc)
    total_chunks = sum(len(v) for v in chunks_by_doc.values())
    sources = [chunks[0].get("doc_filename", "unknown") for chunks in chunks_by_doc.values() if chunks]

    yield {"type": "retrieval", "chunk_count": total_chunks, "sources": sources, "doc_count": doc_count}

    async def map_doc(doc_id: str, chunks: list[dict]) -> DocumentMapResult | None:
        doc_filename = chunks[0].get("doc_filename", doc_id) if chunks else doc_id
        chunks_text = "\n\n".join(
            f"[Chunk {c.get('chunk_index', i)}]\n{c['content']}"
            for i, c in enumerate(sorted(chunks, key=lambda x: x.get("chunk_index", 0)))
        )
        try:
            result = await structured_chat([
                {
                    "role": "system",
                    "content": (
                        "You are a document analyst. Analyse the chunks below relative to the question. "
                        'Respond with JSON only: {"document_name": "<filename>", "key_points": ["point1", "..."], "relevant": true}\n'
                        "Set relevant=true if the document contains information useful for answering the question."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nDocument: {doc_filename}\n\nChunks:\n{chunks_text}",
                },
            ])
            return DocumentMapResult(**result)
        except Exception:
            return None

    tasks = [map_doc(doc_id, chunks) for doc_id, chunks in chunks_by_doc.items()]
    map_results = await asyncio.gather(*tasks)

    valid = [r for r in map_results if r is not None]
    relevant = [r for r in valid if r.relevant] or valid  # fall back to all if none marked relevant

    map_summary = "\n\n".join(
        "Document: {}\nKey Points:\n{}".format(
            r.document_name, "\n".join(f"- {p}" for p in r.key_points)
        )
        for r in relevant
    )

    reduce_context = f"\n\n<full_context_analysis>\n{map_summary}\n</full_context_analysis>"
    messages = [{"role": "system", "content": SYSTEM_PROMPT + reduce_context}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history_data]
    messages = _trim_to_budget(messages)

    async for event in traced_stream_chat(
        messages=messages,
        conversation_id=conversation_id,
        use_tools=False,
        query=question,
        chunk_count=total_chunks,
        sources=sources,
    ):
        yield event


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

        if body.full_context:
            # Full context mode: map-reduce over all indexed documents
            async for event in _full_context_events(body.message, messages_result.data, conversation_id):
                if event["type"] == "retrieval":
                    yield f"data: {json.dumps({'type': 'retrieval', 'query': body.message, 'chunk_count': event['chunk_count'], 'sources': event['sources'], 'mode': 'full_context', 'doc_count': event['doc_count']})}\n\n"
                elif event["type"] == "delta":
                    full_response.append(event["content"])
                    yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"
        else:
            # Standard mode: vector search → top-k chunks → single LLM call
            # 4. Pre-fetch retrieval using the user message directly — runs before any LLM call.
            #    Reduces 2 sequential LLM calls to 1 by injecting context upfront.
            chunks = await retrieval_service.search(body.message)

            # Notify frontend — include unique source filenames for display
            sources = list({c["doc_filename"] for c in chunks}) if chunks else []
            yield f"data: {json.dumps({'type': 'retrieval', 'query': body.message, 'chunk_count': len(chunks), 'sources': sources})}\n\n"

            # Build context block if chunks were found — include source metadata for attribution
            context_block = ""
            if chunks:
                context_lines = "\n\n".join(
                    "[Source: {filename} | Type: {doc_type} | Chunk {idx} | similarity {sim:.2f}]: {content}".format(
                        filename=c["doc_filename"],
                        doc_type=(c.get("doc_metadata") or {}).get("doc_type", "unknown"),
                        idx=c["chunk_index"],
                        sim=c["similarity"],
                        content=c["content"],
                    )
                    for c in chunks
                )
                context_block = f"\n\n<retrieved_context>\n{context_lines}\n</retrieved_context>"

            # 5. Build messages list — context injected into system message
            messages = [{"role": "system", "content": SYSTEM_PROMPT + context_block}]
            messages += [
                {"role": m["role"], "content": m["content"]}
                for m in messages_result.data
            ]
            messages = _trim_to_budget(messages)

            # 6. Single LLM call — no tools needed, context is already in system message
            async for event in traced_stream_chat(
                messages=messages,
                conversation_id=conversation_id,
                use_tools=False,
                query=body.message,
                chunk_count=len(chunks),
                sources=sources,
            ):
                if event["type"] == "delta":
                    full_response.append(event["content"])
                    yield f"data: {json.dumps({'type': 'delta', 'content': event['content']})}\n\n"
                elif event["type"] == "done":
                    break

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
