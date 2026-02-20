import os
from anthropic import AsyncAnthropic
from typing import AsyncGenerator

client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env


async def stream_response(
    messages: list[dict],
    system_prompt: str = "You are a helpful AI assistant.",
) -> AsyncGenerator[str, None]:
    """
    Streams text from Claude given the full conversation history.
    Claude's API is stateless — caller provides complete message history each turn.
    """
    async with client.messages.stream(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
