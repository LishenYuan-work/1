"""Email authentication, verification, password reset, and organizations."""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import create_access_token, create_one_time_token, create_refresh_token, decode_token, hash_one_time_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models import EmailToken, Organization, OrganizationInvite, OrganizationMember, Profile
from app.dependencies import require_user
from app.models.schemas import CreateOrganizationRequest, EmailRequest, InviteMemberRequest, LoginRequest, MemberItem, OrganizationSummary, RefreshRequest, RegisterRequest, ResetPasswordRequest, TokenRequest, TokenResponse, UserProfile
from app.services.email_service import EmailDeliveryError, send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
org_router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _expired(value: datetime) -> bool:
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized < datetime.now(timezone.utc)


def _profile_response(user: Profile, memberships: list[OrganizationMember]) -> TokenResponse:
    orgs = [OrganizationSummary(id=m.organization.id, name=m.organization.name, role=m.role) for m in memberships]
    return TokenResponse(user=UserProfile(id=user.id, email=user.email, display_name=user.display_name, email_verified=bool(user.email_verified_at), organizations=orgs, created_at=str(user.created_at)))


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.app_env.lower() == "production"
    response.set_cookie("review_access", access, httponly=True, secure=secure, samesite="none" if secure else "lax", max_age=settings.access_token_minutes * 60, path="/")
    response.set_cookie("review_refresh", refresh, httponly=True, secure=secure, samesite="none" if secure else "lax", max_age=settings.refresh_token_days * 86400, path="/api/auth")
    response.set_cookie("review_csrf", secrets.token_urlsafe(32), httponly=False, secure=secure, samesite="none" if secure else "lax", max_age=settings.refresh_token_days * 86400, path="/")


async def _load_memberships(db: AsyncSession, user_id: str) -> list[OrganizationMember]:
    result = await db.execute(select(OrganizationMember).options(selectinload(OrganizationMember.organization)).where(OrganizationMember.user_id == user_id))
    return list(result.scalars().all())


async def _send_token(db: AsyncSession, user: Profile, purpose: str, subject: str, path: str, expires: timedelta) -> None:
    raw, token_hash = create_one_time_token()
    db.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=datetime.now(timezone.utc) + expires))
    await db.commit()
    await asyncio.to_thread(send_email, user.email, subject, f'<p>请打开链接完成操作：</p><p><a href="{settings.frontend_url}{path}?token={raw}">继续操作</a></p>')


def _email_error() -> HTTPException:
    return HTTPException(502, "邮件服务拒绝了发送请求，请检查 Resend 的 API Key 和已验证发件地址")


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = str(req.email).lower()
    if await db.scalar(select(Profile).where(Profile.email == email)):
        raise HTTPException(409, "该邮箱已注册")
    user = Profile(email=email, password_hash=hash_password(req.password), display_name=req.display_name or email.split("@")[0])
    db.add(user)
    await db.flush()
    invited = None
    if req.invite_token:
        invited = await db.scalar(select(OrganizationInvite).where(OrganizationInvite.token_hash == hash_one_time_token(req.invite_token), OrganizationInvite.accepted_at.is_(None)))
        if not invited or _expired(invited.expires_at) or invited.email != email:
            raise HTTPException(400, "工作区邀请无效或已过期")
    if invited:
        now = datetime.now(timezone.utc)
        consumed = await db.execute(
            update(OrganizationInvite)
            .where(OrganizationInvite.id == invited.id, OrganizationInvite.accepted_at.is_(None), OrganizationInvite.expires_at > now)
            .values(accepted_at=now)
        )
        if consumed.rowcount != 1:
            raise HTTPException(400, "工作区邀请无效或已使用")
        db.add(OrganizationMember(organization_id=invited.organization_id, user_id=user.id, role="member"))
    else:
        organization = Organization(name=req.organization_name or f"{user.display_name} 的工作区", created_by=user.id)
        db.add(organization)
        await db.flush()
        db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(user)
    try:
        await _send_token(db, user, "verify_email", "验证您的评审平台邮箱", "/verify-email", timedelta(hours=24))
    except EmailDeliveryError as exc:
        raise _email_error() from exc
    memberships = await _load_memberships(db, user.id)
    access, refresh = create_access_token(user.id, token_version=user.token_version), create_refresh_token(user.id, token_version=user.token_version)
    _set_auth_cookies(response, access, refresh)
    return _profile_response(user, memberships)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(Profile).where(Profile.email == str(req.email).lower()))
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    if not user.email_verified_at:
        raise HTTPException(403, "邮箱尚未验证，请先验证邮箱")
    memberships = await _load_memberships(db, user.id)
    access, refresh = create_access_token(user.id, req.remember_me, user.token_version), create_refresh_token(user.id, user.token_version)
    _set_auth_cookies(response, access, refresh)
    return _profile_response(user, memberships)


@router.post("/verify-email")
async def verify_email(req: TokenRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_one_time_token(req.token)
    token = await db.scalar(select(EmailToken).where(EmailToken.token_hash == token_hash, EmailToken.purpose == "verify_email", EmailToken.used_at.is_(None)))
    if not token or _expired(token.expires_at):
        raise HTTPException(400, "验证链接无效或已过期")
    consumed = await db.execute(update(EmailToken).where(EmailToken.id == token.id, EmailToken.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)))
    if consumed.rowcount != 1:
        raise HTTPException(400, "验证链接无效或已使用")
    user = await db.get(Profile, token.user_id)
    user.email_verified_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "verified"}


@router.post("/resend-verification")
async def resend_verification(req: EmailRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(Profile).where(Profile.email == str(req.email).lower()))
    if user and not user.email_verified_at:
        try:
            await _send_token(db, user, "verify_email", "重新验证评审平台邮箱", "/verify-email", timedelta(hours=24))
        except EmailDeliveryError as exc:
            raise _email_error() from exc
    return {"status": "sent"}


@router.post("/forgot-password")
async def forgot_password(req: EmailRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(Profile).where(Profile.email == str(req.email).lower()))
    if user:
        try:
            await _send_token(db, user, "reset_password", "重置评审平台密码", "/reset-password", timedelta(hours=1))
        except EmailDeliveryError as exc:
            raise _email_error() from exc
    return {"status": "sent"}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_one_time_token(req.token), EmailToken.purpose == "reset_password", EmailToken.used_at.is_(None)))
    if not token or _expired(token.expires_at):
        raise HTTPException(400, "重置链接无效或已过期")
    consumed = await db.execute(update(EmailToken).where(EmailToken.id == token.id, EmailToken.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)))
    if consumed.rowcount != 1:
        raise HTTPException(400, "重置链接无效或已使用")
    user = await db.get(Profile, token.user_id)
    user.password_hash = hash_password(req.password)
    user.token_version += 1
    await db.execute(update(EmailToken).where(EmailToken.user_id == user.id, EmailToken.purpose == "reset_password", EmailToken.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"status": "reset"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(response: Response, req: RefreshRequest | None = None, refresh_cookie: str | None = Cookie(default=None, alias="review_refresh"), db: AsyncSession = Depends(get_db)):
    raw_refresh = (req.refresh_token if req else None) or refresh_cookie
    payload = decode_token(raw_refresh, "refresh") if raw_refresh else None
    user = await db.get(Profile, payload["sub"]) if payload else None
    if not user or not user.is_active or not user.email_verified_at or int(payload.get("ver", 0)) != user.token_version:
        raise HTTPException(401, "刷新令牌无效")
    access, refresh_token = create_access_token(user.id, token_version=user.token_version), create_refresh_token(user.id, user.token_version)
    _set_auth_cookies(response, access, refresh_token)
    return _profile_response(user, await _load_memberships(db, user.id))


@router.post("/logout")
async def logout(response: Response, user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    user.token_version += 1
    await db.commit()
    response.delete_cookie("review_access", path="/")
    response.delete_cookie("review_refresh", path="/api/auth")
    response.delete_cookie("review_csrf", path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfile)
async def me(user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    memberships = await _load_memberships(db, user.id)
    return _profile_response(user, memberships).user


@org_router.post("", response_model=OrganizationSummary, status_code=201)
async def create_organization(req: CreateOrganizationRequest, user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    organization = Organization(name=req.name, created_by=user.id)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await db.commit()
    return OrganizationSummary(id=organization.id, name=organization.name, role="owner")


@org_router.get("/{organization_id}/members", response_model=list[MemberItem])
async def list_members(organization_id: str, user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    member = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id))
    if not member:
        raise HTTPException(404, "资源不存在")
    result = await db.execute(select(OrganizationMember).options(selectinload(OrganizationMember.user)).where(OrganizationMember.organization_id == organization_id))
    return [MemberItem(user_id=m.user_id, email=m.user.email, display_name=m.user.display_name, role=m.role, joined_at=str(m.created_at)) for m in result.scalars().all()]


@org_router.post("/{organization_id}/invites")
async def invite_member(organization_id: str, req: InviteMemberRequest, user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    member = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id, OrganizationMember.role == "owner"))
    if not member:
        raise HTTPException(404, "资源不存在")
    raw = secrets.token_urlsafe(32)
    invite = OrganizationInvite(organization_id=organization_id, email=str(req.email).lower(), token_hash=hash_one_time_token(raw), invited_by=user.id, expires_at=datetime.now(timezone.utc) + timedelta(hours=72))
    db.add(invite)
    await db.commit()
    try:
        await asyncio.to_thread(send_email, str(req.email), "加入评审工作区", f'<p><a href="{settings.frontend_url}/register?invite={raw}">接受工作区邀请</a></p>')
    except EmailDeliveryError as exc:
        raise _email_error() from exc
    return {"status": "sent"}


@org_router.delete("/{organization_id}/members/{member_user_id}", status_code=204)
async def remove_member(organization_id: str, member_user_id: str, user: Profile = Depends(require_user), db: AsyncSession = Depends(get_db)):
    owner = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id, OrganizationMember.role == "owner"))
    if not owner or member_user_id == user.id:
        raise HTTPException(404, "资源不存在")
    member = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == member_user_id))
    if not member or member.role == "owner":
        raise HTTPException(404, "资源不存在")
    await db.delete(member)
    await db.commit()
