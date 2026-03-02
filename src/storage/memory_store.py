"""
内存存储 - 替代 Redis（轻量化部署）
"""
from typing import Dict, Optional
import time
from src.config import settings


class MemoryStore:
    """内存存储客户端 - 模拟 Redis"""

    def __init__(self):
        self._store: Dict[str, tuple] = {}  # key -> (value, expire_time)
        self._enabled = bool(settings.REDIS_URL)  # 如果配置了 Redis URL 则启用

    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        if self._enabled:
            # 如果配置了 Redis，应该使用真实的 Redis（这里简化处理）
            return None

        # 检查是否过期
        if key in self._store:
            value, expire_time = self._store[key]
            if expire_time is None or time.time() < expire_time:
                return value
            else:
                del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        if self._enabled:
            return None

        expire_time = None
        if ex is not None:
            expire_time = time.time() + ex
        self._store[key] = (value, expire_time)

    async def setex(self, key: str, value: str, seconds: int):
        """设置值并指定过期时间"""
        if self._enabled:
            return None

        expire_time = time.time() + seconds
        self._store[key] = (value, expire_time)

    async def delete(self, key: str):
        """删除键"""
        if self._enabled:
            return None

        if key in self._store:
            del self._store[key]

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if self._enabled:
            return False

        if key in self._store:
            value, expire_time = self._store[key]
            if expire_time is None or time.time() < expire_time:
                return True
            else:
                del self._store[key]
        return False

    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        if self._enabled:
            return None

        if key in self._store:
            value, _ = self._store[key]
            expire_time = time.time() + seconds
            self._store[key] = (value, expire_time)

    async def close(self):
        """关闭连接（内存存储无需关闭）"""
        pass

    def clear_expired(self):
        """清理过期数据"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expire_time) in self._store.items()
            if expire_time is not None and current_time >= expire_time
        ]
        for key in expired_keys:
            del self._store[key]


# 全局内存存储实例
memory_store = MemoryStore()


# 兼容 Redis 的接口
class RedisClient:
    """兼容 Redis 接口的内存存储"""

    def __init__(self):
        self._store = memory_store

    async def get(self, key: str) -> str:
        """获取值"""
        return await self._store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        return await self._store.set(key, value, ex)

    async def setex(self, key: str, value: str, seconds: int):
        """设置值并指定过期时间"""
        return await self._store.setex(key, value, seconds)

    async def delete(self, key: str):
        """删除键"""
        return await self._store.delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self._store.exists(key)

    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        return await self._store.expire(key, seconds)

    async def close(self):
        """关闭连接"""
        return await self._store.close()


# 全局Redis客户端实例（实际使用内存存储）
redis_client = RedisClient()


def get_session_key(session_key_value: str) -> str:
    """获取会话Redis键"""
    return f"session:{session_key_value}"


def get_waiting_key(session_key_value: str) -> str:
    """获取等待上下文Redis键"""
    return f"waiting:{session_key_value}"
