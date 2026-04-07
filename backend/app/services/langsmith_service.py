import os
from langsmith.run_trees import RunTree
from .openrouter_service import stream_chat
from typing import AsyncGenerator


def _ls_enabled() -> bool:
    return bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))


def _project() -> str:
    return os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT", "default")


def _app_settings() -> tuple[list, list, str]:
    try:
        from .settings_service import get_settings
        s = get_settings()
        return (
            s.get("topic_vocabulary") or [],
            s.get("metadata_schema") or [],
            s.get("chat_model", ""),
        )
    except Exception:
        return [], [], ""


# ---------------------------------------------------------------------------
# Root turn span
# ---------------------------------------------------------------------------

def start_turn_trace(
    query: str,
    conversation_id: str,
    chunk_count: int = 0,
    sources: list[str] | None = None,
) -> RunTree | None:
    """Create and post a root RunTree for one full agentic turn. Returns None if LangSmith is disabled."""
    if not _ls_enabled():
        return None

    topic_vocabulary, metadata_schema, chat_model = _app_settings()

    run = RunTree(
        name="rag_turn",
        run_type="chain",
        inputs={
            "query": query,
            "conversation_id": conversation_id,
            "chunk_count": chunk_count,
            "sources": sources or [],
            "model": chat_model,
            "topic_vocabulary": topic_vocabulary,
            "metadata_schema": metadata_schema,
        },
        tags=topic_vocabulary,
        session_name=_project(),
    )
    run.post()
    return run


def end_turn_trace(run: RunTree | None, final_content: str) -> None:
    """End and patch the root turn span."""
    if run is None:
        return
    run.end(outputs={"content": final_content})
    run.patch()


# ---------------------------------------------------------------------------
# LLM child span
# ---------------------------------------------------------------------------

async def traced_stream_chat(
    messages: list[dict],
    conversation_id: str,
    use_tools: bool = True,
    query: str | None = None,
    chunk_count: int = 0,
    sources: list[str] | None = None,
    parent_run: RunTree | None = None,
) -> AsyncGenerator[dict, None]:
    """Wrap stream_chat with a child LLM span under parent_run (or a root span if none)."""
    if not _ls_enabled():
        async for event in stream_chat(messages, use_tools=use_tools):
            yield event
        return

    _, _, chat_model = _app_settings()

    if parent_run is not None:
        llm_run = parent_run.create_child(
            name="llm_call",
            run_type="llm",
            inputs={"messages": messages, "model": chat_model},
        )
    else:
        # Fallback: standalone root span (backwards-compat if called without parent)
        topic_vocabulary, metadata_schema, chat_model2 = _app_settings()
        llm_run = RunTree(
            name="llm_call",
            run_type="llm",
            inputs={
                "query": query or _last_user_message(messages),
                "conversation_id": conversation_id,
                "messages": messages,
                "model": chat_model,
            },
            session_name=_project(),
        )
    llm_run.post()

    full_content = []
    tool_calls_seen: list[dict] = []
    try:
        async for event in stream_chat(messages, use_tools=use_tools):
            if event["type"] == "delta":
                full_content.append(event["content"])
            elif event["type"] == "tool_calls":
                tool_calls_seen = event["tool_calls"]
            yield event
        llm_run.end(outputs={
            "content": "".join(full_content),
            "tool_calls": tool_calls_seen,
        })
    except Exception as e:
        llm_run.end(error=str(e))
        raise
    finally:
        llm_run.patch()


# ---------------------------------------------------------------------------
# Tool child span
# ---------------------------------------------------------------------------

def record_tool_span(
    parent_run: RunTree | None,
    tool_name: str,
    args: dict,
    result: object,
    error: str | None = None,
) -> None:
    """Record a single synchronous tool call as a child span. Fire-and-forget."""
    if parent_run is None:
        return
    child = parent_run.create_child(
        name=tool_name,
        run_type="tool",
        inputs={"args": args},
    )
    child.post()
    if error:
        child.end(error=error)
    else:
        child.end(outputs={"result": result})
    child.patch()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""
