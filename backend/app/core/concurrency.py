"""
并发控制 — 限制同时运行的辩论数量

保护 DeepSeek API 不被并发请求打爆。
asyncio.Semaphore 实现，零外部依赖。
"""

import asyncio

from app.core.config import settings


class DebateConcurrencyLimit:
    """限制同时运行的辩论数"""

    def __init__(self, max_concurrent: int):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running: set[str] = set()  # 当前正在运行的 debate_id

    async def acquire(self, debate_id: str):
        """获取执行槽位，若已满则等待"""
        await self._semaphore.acquire()
        self._running.add(debate_id)

    def release(self, debate_id: str):
        """释放槽位"""
        self._running.discard(debate_id)
        self._semaphore.release()

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def available_slots(self) -> int:
        return self._semaphore._value


# 全局单例：最多同时运行 5 场辩论
debate_limit = DebateConcurrencyLimit(max_concurrent=settings.max_concurrent_debates)
