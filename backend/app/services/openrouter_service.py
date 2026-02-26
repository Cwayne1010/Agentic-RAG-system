import json
import os
from openai import AsyncOpenAI
from typing import AsyncGenerator
from app.services.settings_service import get_settings

SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools.\n\n"
    "Tool selection guide:\n"
    "- retrieve_documents: Targeted lookups for specific facts or passages from documents.\n"
    "- query_database: Structured questions about document metadata, counts, or conversation history.\n"
    "- web_search: Fallback for current events or when documents don't contain the answer.\n"
    "- spawn_document_agent: Use when the user asks to summarise, deeply analyse, compare, or extract "
    "information from documents. Pass document_name for a single document, or omit it to analyse "
    "the entire knowledge base. Do NOT use for simple keyword questions — use retrieve_documents instead.\n\n"
    "Always cite sources. For documents, cite filename. For web, include URL. "
    "When a sub-agent completes, synthesise its findings into a clear response."
)

RETRIEVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_documents",
        "description": (
            "Search the indexed document knowledge base. Use this when the user asks "
            "about content that may be in their uploaded documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "doc_type_filter": {
                    "type": "string",
                    "description": "Optional: filter by document type (e.g. 'report', 'manual')",
                },
            },
            "required": ["query"],
        },
    },
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use this as a fallback when "
            "the user's documents don't contain the answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Web search query"},
            },
            "required": ["query"],
        },
    },
}

TEXT_TO_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": (
            "Query structured data about the user's documents, conversations, and messages "
            "using natural language. Use this for questions like 'how many documents do I have?', "
            "'what files did I upload last week?', or 'which conversations mentioned X?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question about the user's data",
                },
            },
            "required": ["question"],
        },
    },
}

DOCUMENT_AGENT_TOOL = {
    "type": "function",
    "function": {
        "name": "spawn_document_agent",
        "description": (
            "Delegate document analysis to a specialised sub-agent. Use this when the user asks "
            "to summarise, compare, extract structured information from, or deeply analyse documents. "
            "If a specific document is named, pass it as document_name. "
            "If the question spans the whole knowledge base ('all my documents', 'across everything'), "
            "omit document_name — the sub-agent will scan all documents automatically. "
            "Do NOT use this for simple keyword lookups — use retrieve_documents for those."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "A clear, self-contained instruction describing what analysis to perform.",
                },
                "document_name": {
                    "type": "string",
                    "description": "Optional filename of a specific document to analyse (e.g. 'report.pdf'). "
                                   "Omit to analyse all documents.",
                },
            },
            "required": ["task"],
        },
    },
}

ALL_TOOLS = [RETRIEVAL_TOOL, WEB_SEARCH_TOOL, TEXT_TO_SQL_TOOL, DOCUMENT_AGENT_TOOL]


def _get_llm_client(settings: dict) -> AsyncOpenAI:
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    base_url = settings.get("llm_base_url") or "https://openrouter.ai/api/v1"
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0)


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
        "extra_headers": {"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173")},
    }
    if use_tools:
        kwargs["tools"] = ALL_TOOLS

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


async def structured_chat(messages: list[dict]) -> dict:
    """Non-streaming call returning a JSON object (used for map phase in full context mode)."""
    settings = get_settings()
    client = _get_llm_client(settings)
    model = settings["chat_model"]

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        extra_headers={"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173")},
    )
    return json.loads(response.choices[0].message.content)
