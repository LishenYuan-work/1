"""FastAPI 依赖注入：数据库会话 + 当前用户"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Profile
from app.core.security import verify_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile | None:
    """从 Authorization Header 获取当前用户（可选登录）"""
    if credentials is None:
        return None
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        return None
    result = await db.execute(select(Profile).where(Profile.id == user_id))
    return result.scalar_one_or_none()


async def require_user(
    user: Profile | None = Depends(get_current_user),
) -> Profile:
    """要求必须登录"""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return user
