"""Authentication and organization authorization dependencies."""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.database import get_db
from app.db.models import OrganizationMember, Profile

security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class GuestUser:
    id: str
    email: str = "guest@local.invalid"
    display_name: str = "游客体验"
    email_verified_at: datetime = datetime(2000, 1, 1, tzinfo=timezone.utc)
    is_guest: bool = True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    access_cookie: str | None = Cookie(default=None, alias="review_access"),
    db: AsyncSession = Depends(get_db),
) -> Profile | GuestUser | None:
    raw_token = credentials.credentials if credentials else access_cookie
    if not raw_token:
        return None
    payload = decode_token(raw_token)
    if not payload:
        return None
    if payload.get("guest") is True and str(payload["sub"]).startswith("guest:"):
        return GuestUser(id=str(payload["sub"]))
    user = await db.scalar(select(Profile).where(Profile.id == payload["sub"], Profile.is_active.is_(True)))
    if not user or int(payload.get("ver", 0)) != user.token_version:
        return None
    return user


async def require_user(user: Profile | GuestUser | None = Depends(get_current_user)) -> Profile | GuestUser:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    if not user.email_verified_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "请先验证邮箱")
    return user


async def require_organization_member(
    x_organization_id: str = Header(alias="X-Organization-ID"),
    user: Profile = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == x_organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    return membership
