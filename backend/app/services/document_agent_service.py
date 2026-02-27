"""
Document Sub-Agent Service (Module 8)

Replaces the manual full-context toggle with LLM-driven delegation.

Path A (document_name given):  single doc, full chunk injection, streaming answer
Path B (no document_name):     all docs, parallel map → summary injection, streaming answer

Yields SSE event dicts. The final {"type": "tool_message", "content": str} is a
sentinel captured by chat.py as the tool result — NOT forwarded to the frontend.
"""
import asyncio
import json
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI

from app.services.settings_service import get_settings
from app.services import retrieval_service
from app.services.openrouter_service import structured_chat

MAX_SUB_AGENT_ITERATIONS = 2
DIRECT_INJECT_THRESHOLD = 25  # skip map-reduce below this total chunk count

SUB_AGENT_SYSTEM_PROMPT = (
    "You are a document analysis specialist. Your job is to analyse documents "
    "from the user's knowledge base and answer the given task.\n\n"
    "Be thorough and specific. Cite document names and chunk numbers when quoting.\n"
    "If you cannot find the information, say so explicitly."
)

RETRIEVAL_TOOL_ONLY = {
    "type": "function",
    "function": {
        "name": "retrieve_documents",
        "description": "Search the indexed document knowledge base for relevant chunks.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "doc_type_filter": {"type": "string", "description": "Optional: filter by document type"},
            },
            "required": ["query"],
        },
    },
}


async def _analyze_doc(doc_id: str, chunks: list[dict], task: str, model: str | None = None) -> dict | None:
    """
    Map phase: extract key_points and relevance for one document.
    Mirrors the old map_doc() logic from chat.py.
    """
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
                    "You are a document analyst. Analyse the chunks below relative to the task. "
                    'Respond with JSON only: {"document_name": "<filename>", "key_points": ["point1", "..."], "relevant": true}\n'
                    "Set relevant=true if the document contains information useful for the task."
                ),
            },
            {
                "role": "user",
                "content": f"Task: {task}\n\nDocument: {doc_filename}\n\nChunks:\n{chunks_text}",
            },
        ], model_override=model)
        result["doc_id"] = doc_id
        return result
    except Exception:
        return None


async def run_agent(
    task: str,
    document_name: str | None,
    user_id: str,
) -> AsyncGenerator[dict, None]:
    yield {"type": "sub_agent_start", "task": task, "document_name": document_name}

    settings = get_settings()
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    base_url = settings.get("llm_base_url") or "https://openrouter.ai/api/v1"
    model = settings["chat_model"]
    map_model = settings.get("map_model") or model
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0)

    # sub_agent_model: model used for the final streaming response
    # Path A uses chat_model; Path B uses map_model (fast large-context model)
    sub_agent_model = model

    # ── Path A: single named document ──────────────────────────────────────
    if document_name:
        doc_id = await retrieval_service.find_document_id_by_filename(document_name, user_id)
        injected_context = await retrieval_service.fetch_document_context(doc_id, user_id) if doc_id else None

        if injected_context:
            system = (
                SUB_AGENT_SYSTEM_PROMPT
                + f"\n\n<injected_document>\n{injected_context}\n</injected_document>\n\n"
                "The full document is injected above. Answer the task using it directly."
            )
            messages: list[dict] = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Task: {task}"},
            ]
            use_tools = False
            tools_list: list = []
        else:
            # Named doc not found — fall back to retrieval
            messages = [
                {"role": "system", "content": SUB_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task}\n\nNote: document '{document_name}' was not found. Search the knowledge base instead."},
            ]
            use_tools = True
            tools_list = [RETRIEVAL_TOOL_ONLY]

    # ── Path B: all documents ───────────────────────────────────────────────
    else:
        chunks_by_doc = await retrieval_service.fetch_all_chunks_by_document(user_id)
        doc_count = len(chunks_by_doc)
        total_chunks = sum(len(c) for c in chunks_by_doc.values())

        yield {"type": "sub_agent_scanning", "doc_count": doc_count}

        sub_agent_model = map_model  # Path B always uses the fast model

        if total_chunks <= DIRECT_INJECT_THRESHOLD:
            # ── Path B-fast: inject all chunks directly, single LLM call ──
            parts = []
            for doc_id, chunks in chunks_by_doc.items():
                doc_filename = chunks[0].get("doc_filename", doc_id) if chunks else doc_id
                sorted_chunks = sorted(chunks, key=lambda x: x.get("chunk_index", 0))
                chunks_text = "\n\n".join(
                    f"[Chunk {c.get('chunk_index', i)}]\n{c['content']}"
                    for i, c in enumerate(sorted_chunks)
                )
                parts.append(f'<document name="{doc_filename}">\n{chunks_text}\n</document>')

            yield {
                "type": "sub_agent_map_done",
                "total_docs": doc_count,
                "relevant_docs": doc_count,
                "sources": [
                    chunks[0].get("doc_filename", doc_id)
                    for doc_id, chunks in chunks_by_doc.items() if chunks
                ],
            }

            system = (
                SUB_AGENT_SYSTEM_PROMPT
                + "\n\n<knowledge_base>\n"
                + "\n\n".join(parts)
                + "\n</knowledge_base>\n\n"
                "The full knowledge base is injected above. Answer the task using it directly."
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Task: {task}"},
            ]
            use_tools = False
            tools_list = []

        else:
            # ── Path B-slow: map-reduce with fast map_model ────────────────
            map_tasks = [
                _analyze_doc(doc_id, chunks, task, model=map_model)
                for doc_id, chunks in chunks_by_doc.items()
            ]
            map_results = await asyncio.gather(*map_tasks)

            valid = [r for r in map_results if r is not None]
            relevant = [r for r in valid if r.get("relevant")] or valid

            yield {
                "type": "sub_agent_map_done",
                "total_docs": doc_count,
                "relevant_docs": len(relevant),
                "sources": [r.get("document_name", "") for r in relevant],
            }

            map_summary = "\n\n".join(
                "Document: {}\nKey Points:\n{}".format(
                    r.get("document_name", "unknown"),
                    "\n".join(f"- {p}" for p in r.get("key_points", [])),
                )
                for r in relevant
            )

            system = (
                SUB_AGENT_SYSTEM_PROMPT
                + f"\n\n<corpus_analysis>\n{map_summary}\n</corpus_analysis>\n\n"
                "The above is an analysis of all relevant documents in the user's knowledge base. "
                "Answer the task using this analysis."
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Task: {task}"},
            ]
            use_tools = False
            tools_list = []

    # ── Streaming LLM response (both paths converge here) ──────────────────
    final_answer = ""

    for _iteration in range(MAX_SUB_AGENT_ITERATIONS):
        kwargs: dict = {
            "model": sub_agent_model,
            "messages": messages,
            "stream": True,
            "extra_headers": {"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173")},
        }
        if use_tools and tools_list:
            kwargs["tools"] = tools_list

        response = await client.chat.completions.create(**kwargs)

        full_content = ""
        tool_calls: list[dict] = []

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                full_content += delta.content
                yield {"type": "sub_agent_delta", "content": delta.content}

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    while len(tool_calls) <= idx:
                        tool_calls.append({"id": "", "name": "", "arguments": ""})
                    if tc_delta.id:
                        tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls[idx]["arguments"] += tc_delta.function.arguments

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"])
                except Exception:
                    args = {}

                yield {"type": "sub_agent_tool_call", "tool_name": tc["name"], "args": args}

                if tc["name"] == "retrieve_documents":
                    query = args.get("query", "")
                    doc_type = args.get("doc_type_filter")
                    chunks = await retrieval_service.search(
                        query, top_k=8, doc_type_filter=doc_type, user_id=user_id
                    )
                    if chunks:
                        _sc: dict[str, int] = {}
                        for c in chunks:
                            _sc[c["doc_filename"]] = _sc.get(c["doc_filename"], 0) + 1
                        sources = [{"name": n, "chunks": cnt} for n, cnt in _sc.items()]
                    else:
                        sources = []
                    context_text = (
                        "\n\n".join(
                            "[Source: {fn} | Chunk {idx} | score {sim:.2f}]: {content}".format(
                                fn=c["doc_filename"], idx=c["chunk_index"],
                                sim=c.get("similarity", 0.0), content=c["content"],
                            )
                            for c in chunks
                        )
                        if chunks else f"No chunks matched '{query}'."
                    )
                    yield {"type": "sub_agent_tool_result", "tool_name": tc["name"],
                           "chunk_count": len(chunks), "sources": sources}
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": context_text})
                else:
                    messages.append({"role": "tool", "tool_call_id": tc["id"],
                                     "content": f"Unknown tool: {tc['name']}"})
        else:
            final_answer = full_content
            break

    if not final_answer:
        final_answer = full_content

    yield {"type": "sub_agent_done", "answer": final_answer}
    yield {"type": "tool_message", "content": final_answer}  # sentinel for chat.py — NOT forwarded