"""
应用配置管理
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置类"""

    # 应用信息
    APP_NAME: str = "FeishuClaudeBot"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/feishu_claude.db"
    DATABASE_ECHO: bool = False

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1小时

    # Claude配置
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: Optional[str] = None  # 智谱AI兼容接口
    CLAUDE_MODEL: str = "glm-4.7"
    CLAUDE_MAX_TURNS: int = 50
    CLAUDE_PERMISSION_MODE: str = "acceptEdits"

    # 飞书配置
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_ENCRYPT_KEY: str = ""
    FEISHU_VERIFICATION_TOKEN: str = ""

    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # 新需求判断配置
    NEW_DEMAND_KEYWORDS: list = [
        "新需求", "新问题", "重新开始", "reset", "new",
        "下一个", "另外", "另一个", "另外一个问题"
    ]
    CONTEXT_SIMILARITY_THRESHOLD: float = 0.7
    TIME_GAP_THRESHOLD: int = 1800  # 30分钟

    # 会话配置
    SESSION_TIMEOUT_MINUTES: int = 60  # 1小时
    MAX_SESSIONS_PER_USER: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # 允许额外的字段（如ANTHROPIC_BASE_URL）


# 全局配置实例
settings = Settings()
