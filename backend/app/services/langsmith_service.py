from langsmith import traceable
from .openrouter_service import stream_chat
from typing import AsyncGenerator


@traceable(name="module2_chat", run_type="llm")
async def traced_stream_chat(
    messages: list[dict],
    conversation_id: str,
    use_tools: bool = True,
) -> AsyncGenerator[dict, None]:
    async for event in stream_chat(messages, use_tools=use_tools):
        yield event
