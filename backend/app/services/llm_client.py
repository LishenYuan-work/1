"""OpenAI-compatible DeepSeek client owned by the review domain."""

from typing import Generator
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI
from app.core.config import settings

_client: OpenAI | None = None

class LLMError(Exception):
    pass

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY 未配置")
        _client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=120, max_retries=1)
    return _client

def chat(messages: list[dict], model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> str:
    try:
        result = _get_client().chat.completions.create(model=model or settings.deepseek_model, messages=messages, temperature=settings.default_temperature if temperature is None else temperature, max_tokens=max_tokens or settings.default_max_tokens)
        return result.choices[0].message.content or ""
    except (APIError, APITimeoutError, APIConnectionError) as exc:
        raise LLMError(str(exc)) from exc

def chat_stream(messages: list[dict], model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> Generator[str, None, None]:
    try:
        stream = _get_client().chat.completions.create(model=model or settings.deepseek_model, messages=messages, temperature=settings.default_temperature if temperature is None else temperature, max_tokens=max_tokens or settings.default_max_tokens, stream=True)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except (APIError, APITimeoutError, APIConnectionError) as exc:
        raise LLMError(str(exc)) from exc
