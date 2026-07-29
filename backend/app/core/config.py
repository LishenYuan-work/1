"""应用配置 —— Pydantic Settings，支持 .env 和环境变量"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    app_name: str = "Debate Platform API"
    debug: bool = True
    frontend_url: str = "http://localhost:3000"

    # DeepSeek API（平台统一密钥，后续可改为用户各自配置）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # LLM 默认参数
    default_temperature: float = 0.8
    default_max_tokens: int = 2048
    default_rounds: int = 3

    # 并发控制：最多同时运行多少场辩论
    max_concurrent_debates: int = 5

    # 数据库（SQLite 本地开发，生产用 Supabase PostgreSQL）
    database_url: str = "sqlite+aiosqlite:///./debate.db"

    # JWT
    jwt_secret: str = "debate-platform-secret-change-in-production"

    # Supabase（生产环境）
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_url]
        if self.debug:
            origins.extend(["http://localhost:3000", "http://localhost:5173", "http://localhost:8501"])
        return origins


settings = Settings()
