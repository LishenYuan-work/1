"""
速率限制中间件 — 基于 IP 的滑动窗口计数器

无需 Redis，纯内存实现，适合单进程部署。
生产环境建议换 Redis 版以支持多进程。
"""

import time
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from app.core.config import settings


class RateLimiter:
    """滑动窗口速率限制器"""

    def __init__(self):
        # key -> list of timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        检查是否超出限制。
        key: 限流键（如 IP 地址）
        max_requests: 窗口内最大请求数
        window_seconds: 窗口大小（秒）
        返回 True 表示放行，False 表示限流。
        """
        now = time.time()
        cutoff = now - window_seconds

        async with self._lock:
            # 清理过期记录
            self._windows[key] = [t for t in self._windows[key] if t > cutoff]

            if len(self._windows[key]) >= max_requests:
                return False

            self._windows[key].append(now)
            return True

    def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        """查询剩余可用次数"""
        now = time.time()
        cutoff = now - window_seconds
        recent = [t for t in self._windows.get(key, []) if t > cutoff]
        return max(0, max_requests - len(recent))


# 全局实例
rate_limiter = RateLimiter()


async def check_shared_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Atomically enforce a shared limit through PostgreSQL."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.db.database import async_session
    from app.db.models import RateLimitBucket

    for attempt in range(3):
        now = datetime.now(timezone.utc)
        try:
            async with async_session() as db:
                row = await db.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key).with_for_update())
                if row is None:
                    db.add(RateLimitBucket(key=key, window_started_at=now, request_count=1))
                    await db.commit()
                    return True
                started = row.window_started_at
                started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started.astimezone(timezone.utc)
                age = (now - started).total_seconds()
                if age >= window_seconds:
                    row.window_started_at, row.request_count = now, 1
                    await db.commit()
                    return True
                if row.request_count >= max_requests:
                    await db.rollback()
                    return False
                row.request_count += 1
                await db.commit()
                return True
        except IntegrityError:
            if attempt == 2:
                raise
            continue
    return False


# ========== FastAPI 中间件 ==========

# 每个 IP 每分钟最多启动 5 个评审（保护 API 额度）
REVIEW_CREATE_LIMIT = 5
REVIEW_CREATE_WINDOW = 60

# 每个 IP 每分钟最多 120 次普通请求
GENERAL_LIMIT = 120
GENERAL_WINDOW = 60


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP（支持代理）"""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI 中间件：全局速率限制"""
    from fastapi.responses import JSONResponse

    ip = get_client_ip(request)

    if request.url.path.endswith("/start") and request.method == "POST":
        check = check_shared_limit if settings.rate_limit_backend == "database" else rate_limiter.check
        allowed = await check(f"review:{ip}", REVIEW_CREATE_LIMIT, REVIEW_CREATE_WINDOW)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": f"启动评审太频繁，每{REVIEW_CREATE_WINDOW}秒最多{REVIEW_CREATE_LIMIT}次，请稍后再试"},
            )
    else:
        check = check_shared_limit if settings.rate_limit_backend == "database" else rate_limiter.check
        allowed = await check(f"general:{ip}", GENERAL_LIMIT, GENERAL_WINDOW)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "请求太频繁，请稍后再试"},
            )

    response = await call_next(request)
    return response
