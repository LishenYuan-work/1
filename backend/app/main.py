"""FastAPI entrypoint for the review platform."""

from contextlib import asynccontextmanager
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.core.config import settings
from app.core.rate_limit import rate_limit_middleware
from app.db.database import async_session, init_db
from app.db.models import ReviewSession
from app.routers import auth, reviews


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.app_env.lower() != "production":
        await init_db()
    async with async_session() as db:
        await db.execute(update(ReviewSession).where(ReviewSession.status.in_(["running", "queued"])).values(status="interrupted", current_stage="interrupted", error_message="服务重启，评审已暂停"))
        await db.commit()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def csrf_middleware(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"} and request.cookies.get("review_access"):
        exempt = {
            "/api/auth/login", "/api/auth/register", "/api/auth/verify-email",
            "/api/auth/resend-verification", "/api/auth/forgot-password", "/api/auth/reset-password",
            "/api/auth/supabase/exchange",
        }
        if request.url.path not in exempt:
            expected = request.cookies.get("review_csrf")
            supplied = request.headers.get("X-CSRF-Token")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=403, content={"detail": "CSRF 校验失败"})
    return await call_next(request)


app.middleware("http")(rate_limit_middleware)
app.add_middleware(CORSMiddleware, allow_origin_regex=settings.cors_origin_regex, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(auth.org_router)
app.include_router(reviews.router)


@app.get("/api/health")
async def health():
    from app.core.concurrency import review_limit

    return {"status": "ok", "service": settings.app_name, "reviews_running": review_limit.running_count, "runtime": settings.review_runtime}
