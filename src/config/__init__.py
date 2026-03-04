"""配置模块"""
from .settings import settings
from .constants import (
    SessionState as SessionStateEnum,
    MessageDirection,
    SessionType,
    InfoType,
    ClaudeToolName,
    MCPToolName,
    REDIS_KEY_SESSION,
    REDIS_KEY_WAITING,
)

# 为了方便使用，直接导出枚举值
ACTIVE = "active"
CREATED = "created"
WAITING_FOR_USER = "waiting_for_user"
PAUSED = "paused"
COMPLETED = "completed"
EXPIRED = "expired"

# 兼容：保留 SessionState 作为枚举类
SessionState = SessionStateEnum

__all__ = [
    "settings",
    "SessionState",
    "MessageDirection",
    "SessionType",
    "InfoType",
    "ClaudeToolName",
    "MCPToolName",
    "REDIS_KEY_SESSION",
    "REDIS_KEY_WAITING",
]
