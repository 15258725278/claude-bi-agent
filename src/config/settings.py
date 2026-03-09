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
    CLAUDE_WORK_DIR: str = "~"  # Claude SDK 工作目录
    CLAUDE_SKILLS_DIRS: str = "~/.claude/skills,/root/claude-bi-agent/.claude/skills"  # Claude SDK 技能目录（逗号分隔）

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
    NEW_DEMAND_KEYWORDS: str = "新需求,新问题,重新开始,reset,new,下一个,另外,另一个,另外一个问题"
    CONTEXT_SIMILARITY_THRESHOLD: float = 0.7
    TIME_GAP_THRESHOLD: int = 1800  # 30分钟

    # 会话配置
    SESSION_TIMEOUT_MINUTES: int = 60  # 1小时
    MAX_SESSIONS_PER_USER: int = 10

    # 群聊配置
    GROUP_CHAT_ENABLED: bool = True                      # 是否启用群聊功能
    DEMAND_TRIGGER_KEYWORD: str = "帮我处理需求"          # 需求触发关键词

    # 话题配置
    THREAD_AUTO_CREATE: bool = True                     # 是否自动创建话题
    THREAD_TITLE_PREFIX: str = "【需求】"               # 话题标题前缀

    # 需求配置
    DEMAND_STATUS_PENDING: str = "pending"               # 待处理
    DEMAND_STATUS_SCOPE_CONFIRMED: str = "scope_confirmed"  # 口径已确认
    DEMAND_STATUS_ANALYZING: str = "analyzing"           # 分析中
    DEMAND_STATUS_WAITING_FEEDBACK: str = "waiting_feedback"  # 待反馈
    DEMAND_STATUS_COMPLETED: str = "completed"           # 已完成
    DEMAND_STATUS_CANCELLED: str = "cancelled"           # 已取消

    # 将逗号分隔的字符串转换为列表的属性
    @property
    def skills_dirs_list(self) -> list:
        """获取技能目录列表"""
        return [d.strip() for d in self.CLAUDE_SKILLS_DIRS.split(",") if d.strip()]

    @property
    def new_demand_keywords_list(self) -> list:
        """获取新需求关键词列表"""
        return [k.strip() for k in self.NEW_DEMAND_KEYWORDS.split(",") if k.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # 允许额外的字段（如ANTHROPIC_BASE_URL）


# 全局配置实例
settings = Settings()
