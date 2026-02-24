import os
from openai import AsyncOpenAI
from typing import AsyncGenerator
from app.services.settings_service import get_settings

SYSTEM_PROMPT = (
    "You are a helpful AI assistant. When relevant document context is provided "
    "in <retrieved_context> tags, use it to answer the user's question and cite "
    "the source. If no context is provided, answer from your general knowledge."
)

# RETRIEVAL_TOOL is retained for future tool-calling modules (Module 7+).
# It is not currently used — retrieval is now pre-fetched before the LLM call.
RETRIEVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_documents",
        "description": (
            "Search the document knowledge base for relevant information. "
            "Use this when the user asks about topics that may be in their uploaded documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant document chunks",
                }
            },
            "required": ["query"],
        },
    },
}


def _get_llm_client(settings: dict) -> AsyncOpenAI:
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    base_url = settings.get("llm_base_url") or "https://openrouter.ai/api/v1"
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def stream_chat(
    messages: list[dict],
    use_tools: bool = True,
) -> AsyncGenerator[dict, None]:
    """
    Async generator yielding events:
      {"type": "delta", "content": str}
      {"type": "tool_calls", "tool_calls": list[dict]}
      {"type": "done", "content": str, "tool_calls": list[dict]}
    """
    settings = get_settings()
    client = _get_llm_client(settings)
    model = settings["chat_model"]

    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
        "extra_headers": {"HTTP-Referer": "http://localhost:5173"},
    }
    if use_tools:
        kwargs["tools"] = [RETRIEVAL_TOOL]

    response = await client.chat.completions.create(**kwargs)

    full_content = ""
    tool_calls: list[dict] = []

    async for chunk in response:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta

        if delta.content:
            full_content += delta.content
            yield {"type": "delta", "content": delta.content}

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
        yield {"type": "tool_calls", "tool_calls": tool_calls}

    yield {"type": "done", "content": full_content, "tool_calls": tool_calls}
