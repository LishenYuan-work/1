"""配置管理 — 从环境变量加载 DeepSeek API 配置"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """全局配置单例"""

    # DeepSeek API
    api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 辩论默认参数
    default_temperature: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.8"))
    default_max_tokens: int = int(os.getenv("DEFAULT_MAX_TOKENS", "2048"))
    default_rounds: int = int(os.getenv("DEFAULT_ROUNDS", "3"))

    @classmethod
    def validate(cls) -> bool:
        """验证 API Key 是否已配置"""
        if not cls.api_key:
            raise ValueError(
                "未找到 DEEPSEEK_API_KEY！\n"
                "请复制 .env.example 为 .env 并填入你的 API Key。\n"
                "获取 Key: https://platform.deepseek.com/api_keys"
            )
        return True


# 全局配置实例
config = Config()
