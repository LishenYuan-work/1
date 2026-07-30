"""FastAPI 主入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import rate_limit_middleware
from app.db.database import init_db
from app.routers import debates, templates, auth, comments, fact_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动：初始化数据库 + 安全检查"""
    await init_db()

    # 清理卡住的辩论（上次崩溃遗留的 running 状态）
    from app.db.models import Debate
    from sqlalchemy import update
    from app.db.database import async_session
    async with async_session() as db:
        await db.execute(
            update(Debate).where(Debate.status == "running").values(status="failed", error_message="服务器重启，辩论中断")
        )
        await db.commit()
        print("[OK] 已清理卡住的辩论")

    # 校验 API Key
    if not settings.deepseek_api_key or settings.deepseek_api_key.startswith("sk-your"):
        print("警告: DEEPSEEK_API_KEY 未设置或为占位符，辩论功能不可用")
    elif settings.debug:
        masked = settings.deepseek_api_key[:8] + "****" + settings.deepseek_api_key[-4:]
        print(f"[OK] DeepSeek API Key: {masked}")
        print(f"     模型: {settings.deepseek_model}")
        print(f"     最大并发辩论: {settings.max_concurrent_debates}")

    # 校验 JWT Secret
    if settings.jwt_secret == "debate-platform-secret-change-in-production":
        print("警告: JWT_SECRET 为默认值，生产环境请更换")

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# ====== 中间件（顺序重要：后添加的先执行）======

# 1. 速率限制（最外层）
app.middleware("http")(rate_limit_middleware)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== 路由 ======

app.include_router(debates.router)
app.include_router(templates.router)
app.include_router(auth.router)
app.include_router(comments.router)
app.include_router(fact_check.router)


@app.get("/api/health")
async def health():
    from app.core.concurrency import debate_limit
    return {
        "status": "ok",
        "service": settings.app_name,
        "debates_running": debate_limit.running_count,
    }



