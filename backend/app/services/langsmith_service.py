import os
from langsmith.run_trees import RunTree
from .openrouter_service import stream_chat
from typing import AsyncGenerator


async def traced_stream_chat(
    messages: list[dict],
    conversation_id: str,
    use_tools: bool = True,
    query: str | None = None,
    chunk_count: int = 0,
    sources: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    ls_enabled = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))

    if not ls_enabled:
        async for event in stream_chat(messages, use_tools=use_tools):
            yield event
        return

    # Pull app settings for trace enrichment
    try:
        from .settings_service import get_settings
        settings = get_settings()
        topic_vocabulary: list[str] = settings.get("topic_vocabulary") or []
        metadata_schema: list[dict] = settings.get("metadata_schema") or []
        chat_model: str = settings.get("chat_model", "")
    except Exception:
        topic_vocabulary, metadata_schema, chat_model = [], [], ""

    run = RunTree(
        name="rag_chat",
        run_type="llm",
        inputs={
            "query": query or _last_user_message(messages),
            "conversation_id": conversation_id,
            "chunk_count": chunk_count,
            "sources": sources or [],
            "topic_vocabulary": topic_vocabulary,
            "metadata_schema": metadata_schema,
            "model": chat_model,
            "messages": messages,
        },
        tags=topic_vocabulary,
        session_name=os.getenv("LANGCHAIN_PROJECT", "default"),
    )
    run.post()

    full_content = []
    try:
        async for event in stream_chat(messages, use_tools=use_tools):
            if event["type"] == "delta":
                full_content.append(event["content"])
            yield event
        run.end(outputs={"content": "".join(full_content)})
    except Exception as e:
        run.end(error=str(e))
        raise
    finally:
        run.patch()


def _last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""
