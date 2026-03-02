"""
常量定义
"""
from enum import Enum


class SessionState(Enum):
    """会话状态"""
    CREATED = "created"
    ACTIVE = "active"
    WAITING_FOR_USER = "waiting_for_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"


class MessageDirection(Enum):
    """消息方向"""
    USER = "user"
    BOT = "bot"


class SessionType(Enum):
    """会话类型"""
    THREAD = "thread"      # 回复链模式（简单对话）
    CARD = "card"          # 卡片模式（复杂任务）
    HYBRID = "hybrid"      # 混合模式


class InfoType(Enum):
    """信息收集类型"""
    TEXT = "text"
    FORM = "form"
    CARD = "card"


# Claude SDK 工具名称
class ClaudeToolName(Enum):
    """Claude工具名称"""
    ASK_USER_FOR_INFO = "ask_user_for_info"
    SEND_MESSAGE = "send_message"
    UPDATE_CARD = "update_card"


# MCP工具名称（带前缀）
class MCPToolName(Enum):
    """MCP工具名称"""
    FEISHU_ASK_USER_FOR_INFO = "mcp__feishu__ask_user_for_info"
    FEISHU_SEND_MESSAGE = "mcp__feishu__send_message"
    FEISHU_UPDATE_CARD = "mcp__feishu__update_card"


# Redis Key 前缀
REDIS_PREFIX = "feishu_claude:"
REDIS_KEY_SESSION = f"{REDIS_PREFIX}session:"
REDIS_KEY_WAITING = f"{REDIS_PREFIX}waiting:"
REDIS_KEY_USER_SESSIONS = f"{REDIS_PREFIX}user_sessions:"
