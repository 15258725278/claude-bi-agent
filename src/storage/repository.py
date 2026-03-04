"""
数据仓库
"""
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Session, Message, Card, WaitingContext
from src.storage.memory_store import redis_client, get_session_key, get_waiting_key
from src.storage.database import AsyncSessionLocal
from src.config import settings, ACTIVE, EXPIRED


class SessionRepository:
    """会话仓库 - 每次方法调用时创建新会话"""

    def __init__(self, db: Optional[AsyncSession] = None):
        # 支持传入会话对象（向后兼容），但不在构造函数中使用
        pass

    async def _get_session(self) -> AsyncSession:
        """获取新的数据库会话"""
        return AsyncSessionLocal()

    async def create(self, session: Session) -> Session:
        """创建会话"""
        async with self._get_session() as db:
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session

    async def get_by_key(self, session_key: str) -> Optional[Session]:
        """根据键获取会话"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session).where(Session.session_key == session_key)
            )
            return result.scalars().first()

    async def get_by_root_id(self, user_id: str, root_id: str) -> Optional[Session]:
        """根据用户ID和根消息ID获取会话"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session).where(
                    and_(Session.user_id == user_id, Session.root_id == root_id)
                )
            )
            return result.scalars().first()

    async def get_by_card_id(self, card_id: str) -> Optional[Session]:
        """根据卡片ID获取会话"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session).where(Session.card_id == card_id)
            )
            return result.scalars().first()

    async def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Session]:
        """获取用户的所有会话"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session)
                .where(Session.user_id == user_id)
                .order_by(Session.updated_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def update(self, session: Session) -> Session:
        """更新会话"""
        async with self._get_session() as db:
            session.updated_at = datetime.now()
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session

    async def update_state(self, session_key: str, state: str) -> None:
        """更新会话状态"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session).where(Session.session_key == session_key)
            )
            session = result.scalars().first()
            if session:
                session.state = state
                session.updated_at = datetime.now()
                await db.commit()

    async def delete(self, session_key: str) -> bool:
        """删除会话"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Session).where(Session.session_key == session_key)
            )
            session = result.scalars().first()
            if session:
                await db.delete(session)
                await db.commit()
                return True
            return False

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        async with self._get_session() as db:
            now = datetime.now()
            result = await db.execute(
                select(Session).where(
                    and_(
                        Session.expires_at.isnot(None),
                        Session.expires_at < now
                    )
                )
            )
            sessions = list(result.scalars().all())
            for session in sessions:
                session.state = EXPIRED
            await db.commit()
            return len(sessions)


class MessageRepository:
    """消息仓库 - 每次方法调用时创建新会话"""

    def __init__(self, db: Optional[AsyncSession] = None):
        # 支持传入会话对象（向后兼容），但不在构造函数中使用
        pass

    async def _get_session(self) -> AsyncSession:
        """获取新的数据库会话"""
        return AsyncSessionLocal()

    async def create(self, message: Message) -> Message:
        """创建消息"""
        async with self._get_session() as db:
            db.add(message)
            await db.commit()
            await db.refresh(message)
            return message

    async def get_by_session_key(
        self,
        session_key: str,
        limit: int = 50
    ) -> List[Message]:
        """获取会话的所有消息"""
        async with self._get_session() as db:
            result = await db.execute(
                select(Message)
                .where(Message.session_key == session_key)
                .order_by(Message.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())


class WaitingContextRepository:
    """等待上下文仓库（Redis）"""

    async def save(self, session_key: str, context: WaitingContext, ttl: int = None) -> None:
        """保存等待上下文"""
        if ttl is None:
            ttl = settings.REDIS_CACHE_TTL
        redis_key = get_waiting_key(session_key)
        await redis_client.setex(redis_key, context.to_json(), ttl)

    async def get(self, session_key: str) -> Optional[WaitingContext]:
        """获取等待上下文"""
        redis_key = get_waiting_key(session_key)
        data = await redis_client.get(redis_key)
        if data:
            return WaitingContext.from_json(data)
        return None

    async def delete(self, session_key: str) -> bool:
        """删除等待上下文"""
        redis_key = get_waiting_key(session_key)
        return await redis_client.delete(redis_key)

    async def exists(self, session_key: str) -> bool:
        """检查等待上下文是否存在"""
        redis_key = get_waiting_key(session_key)
        return await redis_client.exists(redis_key)
