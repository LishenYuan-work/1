"""认证路由：注册、登录、Token 刷新、用户信息"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Profile
from app.dependencies import require_user
from app.models.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserProfile,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ========== 注册 ==========

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    # 检查用户名是否已存在
    existing = await db.execute(select(Profile).where(Profile.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = Profile(
        username=req.username,
        password_hash=hash_password(req.password),
        email=req.email,
        display_name=req.display_name or req.username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            created_at=str(user.created_at),
        ),
    )


# ========== 登录 ==========

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户名 + 密码登录"""
    result = await db.execute(select(Profile).where(Profile.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            created_at=str(user.created_at),
        ),
    )


# ========== 刷新 Token ==========

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """用 refresh_token 换新的 access_token"""
    user_id = verify_token(req.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    result = await db.execute(select(Profile).where(Profile.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            created_at=str(user.created_at),
        ),
    )


# ========== 当前用户 ==========

@router.get("/me", response_model=UserProfile)
async def get_me(user: Profile = Depends(require_user)):
    """获取当前登录用户信息"""
    return UserProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        created_at=str(user.created_at),
    )
