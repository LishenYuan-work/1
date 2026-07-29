"""DeepSeek API 封装 — 基于 OpenAI 兼容接口"""

from typing import Generator
from openai import OpenAI

from src.config import config


def _create_client() -> OpenAI:
    """创建 DeepSeek API 客户端"""
    config.validate()
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """同步调用 DeepSeek Chat，返回完整回复文本"""
    client = _create_client()

    response = client.chat.completions.create(
        model=model or config.model,
        messages=messages,
        temperature=temperature or config.default_temperature,
        max_tokens=max_tokens or config.default_max_tokens,
    )

    return response.choices[0].message.content or ""


def chat_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Generator[str, None, None]:
    """流式调用 DeepSeek Chat，逐块 yield 回复文本"""
    client = _create_client()

    stream = client.chat.completions.create(
        model=model or config.model,
        messages=messages,
        temperature=temperature or config.default_temperature,
        max_tokens=max_tokens or config.default_max_tokens,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
