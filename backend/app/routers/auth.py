"""认证路由：手机号注册/登录、Token 刷新、游客模式、用户信息"""

import uuid

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


def _profile_to_response(p: Profile, access_token: str, refresh_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserProfile(
            id=p.id,
            phone=p.phone,
            display_name=p.display_name,
            is_guest=p.is_guest,
            created_at=str(p.created_at),
        ),
    )


# ========== 注册 ==========

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """手机号注册"""
    existing = await db.execute(select(Profile).where(Profile.phone == req.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该手机号已注册，请直接登录")

    user = Profile(
        phone=req.phone,
        password_hash=hash_password(req.password),
        display_name=req.display_name or f"用户{req.phone[-4:]}",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return _profile_to_response(
        user,
        create_access_token(user.id, remember_me=True),
        create_refresh_token(user.id),
    )


# ========== 登录 ==========

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """手机号 + 密码登录"""
    result = await db.execute(select(Profile).where(Profile.phone == req.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    return _profile_to_response(
        user,
        create_access_token(user.id, remember_me=req.remember_me),
        create_refresh_token(user.id),
    )


# ========== 游客模式 ==========

@router.post("/guest", response_model=TokenResponse, status_code=201)
async def guest_login(db: AsyncSession = Depends(get_db)):
    """游客一键登录（不保留历史记录）"""
    guest_id = uuid.uuid4().hex[:12]
    user = Profile(
        id=guest_id,
        phone=f"guest_{guest_id[:8]}",
        password_hash="",
        display_name="游客",
        is_guest=True,
    )
    db.add(user)
    await db.commit()

    return _profile_to_response(
        user,
        create_access_token(user.id, remember_me=False),  # 游客不跨会话
        "",
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

    return _profile_to_response(
        user,
        create_access_token(user.id, remember_me=True),
        create_refresh_token(user.id),
    )


# ========== 当前用户 ==========

@router.get("/me", response_model=UserProfile)
async def get_me(user: Profile = Depends(require_user)):
    """获取当前登录用户信息"""
    return UserProfile(
        id=user.id,
        phone=user.phone if not user.is_guest else "",
        display_name=user.display_name,
        is_guest=user.is_guest,
        created_at=str(user.created_at),
    )


# ========== 退出游客（清除数据）==========

@router.post("/clear-guest", status_code=204)
async def clear_guest(user: Profile = Depends(require_user)):
    """游客退出时清除所有关联数据"""
    if not user.is_guest:
        raise HTTPException(400, "仅游客可执行此操作")
    # 游客数据会通过 debate.creator_id 的 ON DELETE SET NULL 自动解除关联
    # 这里不做物理删除，前端切换 sessionStorage 即可
