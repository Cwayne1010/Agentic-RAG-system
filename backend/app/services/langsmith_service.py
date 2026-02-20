from langsmith import traceable
from .claude_service import stream_response
from typing import AsyncGenerator


@traceable(name="module1_chat", run_type="llm")
async def traced_stream_response(
    messages: list[dict],
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    async for text in stream_response(messages):
        yield text
