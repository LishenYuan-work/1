"""Limit concurrent review jobs."""

import asyncio

from app.core.config import settings


class ReviewConcurrencyLimit:
    def __init__(self, max_concurrent: int):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running: set[str] = set()

    async def acquire(self, session_id: str):
        await self._semaphore.acquire()
        self._running.add(session_id)

    def release(self, session_id: str):
        self._running.discard(session_id)
        self._semaphore.release()

    @property
    def running_count(self) -> int:
        return len(self._running)


review_limit = ReviewConcurrencyLimit(settings.max_concurrent_reviews)
