"""Application configuration for the review platform."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi-Agent Review Platform API"
    app_env: str = "development"
    debug: bool = True
    frontend_url: str = "http://localhost:3000"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    default_temperature: float = 0.3
    default_max_tokens: int = 4096
    default_rounds: int = 3
    max_concurrent_reviews: int = 5

    database_url: str = "sqlite+aiosqlite:///./review_platform.db"
    jwt_secret: str = "review-platform-secret-change-in-production"
    access_token_minutes: int = 1440
    refresh_token_days: int = 7
    guest_session_minutes: int = 60

    email_provider: str = "console"
    resend_api_key: str = ""
    email_from: str = "Review Platform <noreply@example.com>"
    auth_provider: str = "custom"

    storage_provider: str = "local"
    local_storage_path: str = ".data/uploads"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "review-documents"

    review_runtime: str = "custom"
    max_upload_files: int = 5
    max_upload_bytes: int = 20 * 1024 * 1024
    document_chunk_chars: int = 12000
    max_document_chars: int = 500000
    trust_proxy_headers: bool = False
    rate_limit_backend: str = "memory"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production(self):
        if self.app_env.lower() == "production":
            if self.debug:
                raise ValueError("生产环境必须关闭 DEBUG")
            if self.jwt_secret == "review-platform-secret-change-in-production" or len(self.jwt_secret) < 32:
                raise ValueError("生产环境必须配置至少 32 位随机 JWT_SECRET")
            if self.database_url.startswith("sqlite"):
                raise ValueError("生产环境必须使用 PostgreSQL DATABASE_URL")
            if self.storage_provider != "supabase" or not self.supabase_url or not self.supabase_service_role_key:
                raise ValueError("生产环境必须配置 Supabase Storage")
            if self.auth_provider.lower() == "supabase":
                if not self.supabase_url or not (self.supabase_anon_key or self.supabase_service_role_key):
                    raise ValueError("Supabase Auth 需要配置 SUPABASE_URL 和密钥")
            elif self.email_provider != "resend" or not self.resend_api_key:
                raise ValueError("生产环境必须配置 Resend 或启用 Supabase Auth")
            if self.review_runtime == "langgraph" and not self.database_url.startswith("postgresql"):
                raise ValueError("LangGraph 生产运行时必须使用 PostgreSQL checkpoint")
            if self.rate_limit_backend == "database" and self.database_url.startswith("sqlite"):
                raise ValueError("数据库限流后端需要 PostgreSQL")
            if self.rate_limit_backend != "database":
                raise ValueError("生产环境必须使用数据库共享限流")
        return self

    @property
    def local_storage_dir(self) -> Path:
        return Path(self.local_storage_path).resolve()

    @property
    def cors_origin_regex(self) -> str:
        import re

        patterns = [] if self.app_env.lower() == "production" else [r"http://localhost:\d+"]
        if self.frontend_url:
            patterns.append(re.escape(self.frontend_url.rstrip("/")))
        # Vercel creates a unique preview hostname for each branch deployment.
        # Keep the allow-list limited to this project's review branch so preview
        # builds can authenticate without opening CORS to arbitrary origins.
        if self.app_env.lower() == "production":
            # Vercel uses both branch aliases and immutable deployment aliases.
            # This project is deployed under the `1` Vercel project slug, so
            # permit only its generated hosts; other Vercel projects remain
            # rejected unless explicitly listed through FRONTEND_URL.
            patterns.append(
                r"https://(?:1\.vercel\.app|1-git-refactor-review\.vercel\.app|1(?:-git-refactor-review)?-[a-z0-9-]+\.vercel\.app)"
            )
        return r"^(" + "|".join(patterns) + r")$"


settings = Settings()
