"""Async-friendly wrapper around the existing OpenAI-compatible DeepSeek client."""

import asyncio
import json
from typing import Any, Awaitable, Callable, Generator

from app.core.config import settings


def _sync_chat(messages: list[dict[str, str]], max_tokens: int | None = None) -> str:
    from app.services.llm_client import chat

    return chat(messages, model=settings.deepseek_model, temperature=settings.default_temperature, max_tokens=max_tokens or settings.default_max_tokens)


def _sync_stream(messages: list[dict[str, str]]) -> Generator[str, None, None]:
    from app.services.llm_client import chat_stream

    yield from chat_stream(messages, model=settings.deepseek_model, temperature=settings.default_temperature, max_tokens=settings.default_max_tokens)


async def chat(messages: list[dict[str, str]], max_tokens: int | None = None) -> str:
    return await asyncio.to_thread(_sync_chat, messages, max_tokens)


async def _stream_text(messages: list[dict[str, str]], on_chunk: Callable[[str], Awaitable[None]]) -> str:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()

    def producer() -> None:
        try:
            for chunk in _sync_stream(messages):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except BaseException as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)

    thread = asyncio.create_task(asyncio.to_thread(producer))
    parts: list[str] = []
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            parts.append(item)
            await on_chunk(item)
    finally:
        await thread
    return "".join(parts)


async def structured(messages: list[dict[str, str]], fallback: dict[str, Any], on_chunk: Callable[[str], Awaitable[None]] | None = None) -> dict[str, Any]:
    """Parse model JSON or fail explicitly after one retry."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = await _stream_text(messages, on_chunk) if on_chunk else await chat(messages)
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(raw[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            last_error = ValueError("模型未返回合法 JSON 对象")
        except Exception as exc:
            last_error = exc
        if attempt == 0:
            messages = [*messages, {"role": "system", "content": "上一次输出无法解析。请只输出合法 JSON 对象，不要 Markdown 代码围栏。"}]
    raise ValueError("模型结构化输出失败") from last_error
