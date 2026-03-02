"""存储模块"""
from .database import get_db, init_db, close_db, engine, AsyncSessionLocal
# 使用内存存储替代 Redis
try:
    from .memory_store import redis_client, get_session_key, get_waiting_key
except ImportError:
    from .redis_client import redis_client, get_session_key, get_waiting_key
from .repository import (
    SessionRepository,
    MessageRepository,
    WaitingContextRepository,
)

__all__ = [
    "get_db",
    "init_db",
    "close_db",
    "engine",
    "AsyncSessionLocal",
    "redis_client",
    "get_session_key",
    "get_waiting_key",
    "SessionRepository",
    "MessageRepository",
    "WaitingContextRepository",
]
