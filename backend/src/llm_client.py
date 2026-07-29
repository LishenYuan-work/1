"""DeepSeek API 封装 — 基于 OpenAI 兼容接口"""

import time
from typing import Generator
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from src.config import config


class LLMError(Exception):
    """LLM 调用异常（供上层统一处理）"""
    pass


# 模块级单例 client（避免每次调用重建连接）
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """获取或创建 OpenAI 客户端单例"""
    global _client
    if _client is None:
        config.validate()
        _client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=120.0,  # 120 秒超时
            max_retries=1,  # SDK 层重试 1 次
        )
    return _client


def _handle_api_error(e: Exception, operation: str) -> LLMError:
    """统一将 OpenAI SDK 异常转为 LLMError"""
    if isinstance(e, APITimeoutError):
        return LLMError(f"API 超时: {operation} - {e}")
    elif isinstance(e, APIConnectionError):
        return LLMError(f"API 连接失败: {operation} - {e}")
    elif isinstance(e, APIError):
        return LLMError(f"API 错误 (HTTP {e.status_code}): {operation} - {e}")
    else:
        return LLMError(f"未知错误: {operation} - {e}")


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """同步调用 DeepSeek Chat，返回完整回复文本"""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=model or config.model,
            messages=messages,
            temperature=temperature or config.default_temperature,
            max_tokens=max_tokens or config.default_max_tokens,
        )
        return response.choices[0].message.content or ""
    except (APIError, APITimeoutError, APIConnectionError) as e:
        raise _handle_api_error(e, "同步调用") from e
    except Exception as e:
        raise LLMError(f"未知错误: 同步调用 - {e}") from e


def chat_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Generator[str, None, None]:
    """流式调用 DeepSeek Chat，逐块 yield 回复文本"""
    client = _get_client()

    try:
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
    except (APIError, APITimeoutError, APIConnectionError) as e:
        raise _handle_api_error(e, "流式调用") from e
    except Exception as e:
        raise LLMError(f"未知错误: 流式调用 - {e}") from e
