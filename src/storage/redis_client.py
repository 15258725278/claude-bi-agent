"""
Redis客户端管理
支持Redis禁用时的内存存储回退
"""
import redis.asyncio as redis
from src.config import settings, REDIS_KEY_SESSION, REDIS_KEY_WAITING


class RedisClient:
    """Redis客户端封装"""

    def __init__(self):
        # 检查是否启用Redis
        if settings.REDIS_URL and settings.REDIS_URL.strip():
            try:
                self.redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
                self.enabled = True
            except Exception as e:
                print(f"Redis连接失败，使用内存存储: {e}")
                self.redis = None
                self.enabled = False
        else:
            print("Redis未配置，使用内存存储")
            self.redis = None
            self.enabled = False

        # 内存存储（回退方案）
        self._memory_store = {}

    async def get(self, key: str) -> str:
        """获取值"""
        if self.enabled:
            return await self.redis.get(key)
        else:
            return self._memory_store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        if self.enabled:
            return await self.redis.set(key, value, ex=ex)
        else:
            self._memory_store[key] = value

    async def setex(self, key: str, value: str, seconds: int):
        """设置值并指定过期时间"""
        if self.enabled:
            return await self.redis.setex(key, seconds, value)
        else:
            self._memory_store[key] = value
            # 内存存储不支持自动过期，但可以在这里实现

    async def delete(self, key: str):
        """删除键"""
        if self.enabled:
            return await self.redis.delete(key)
        else:
            self._memory_store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if self.enabled:
            return await self.redis.exists(key) > 0
        else:
            return key in self._memory_store

    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        if self.enabled:
            return await self.redis.expire(key, seconds)
        else:
            # 内存存储不支持自动过期
            pass

    async def close(self):
        """关闭连接"""
        if self.enabled and self.redis:
            await self.redis.close()
        self._memory_store.clear()


# 全局Redis客户端实例
redis_client = RedisClient()


def get_session_key(session_key_value: str) -> str:
    """获取会话Redis键"""
    return f"{REDIS_KEY_SESSION}{session_key_value}"


def get_waiting_key(session_key_value: str) -> str:
    """获取等待上下文Redis键"""
    return f"{REDIS_KEY_WAITING}{session_key_value}"
