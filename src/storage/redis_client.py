"""
Redis客户端管理
"""
import redis.asyncio as redis
from src.config import settings, REDIS_KEY_SESSION, REDIS_KEY_WAITING


class RedisClient:
    """Redis客户端封装"""

    def __init__(self):
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def get(self, key: str) -> str:
        """获取值"""
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        return await self.redis.set(key, value, ex=ex)

    async def setex(self, key: str, value: str, seconds: int):
        """设置值并指定过期时间"""
        return await self.redis.setex(key, seconds, value)

    async def delete(self, key: str):
        """删除键"""
        return await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self.redis.exists(key) > 0

    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        return await self.redis.expire(key, seconds)

    async def close(self):
        """关闭连接"""
        await self.redis.close()


# 全局Redis客户端实例
redis_client = RedisClient()


def get_session_key(session_key_value: str) -> str:
    """获取会话Redis键"""
    return f"{REDIS_KEY_SESSION}{session_key_value}"


def get_waiting_key(session_key_value: str) -> str:
    """获取等待上下文Redis键"""
    return f"{REDIS_KEY_WAITING}{session_key_value}"
