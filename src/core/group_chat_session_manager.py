"""
群聊会话管理器
"""
from typing import Optional
from datetime import datetime
from src.claude import ClaudeSessionManager
from src.storage import SessionRepository, AsyncSessionLocal
from src.feishu import FeishuClient
from src.core.group_chat_router import GroupMessageEvent, GroupMessageMode
from src.utils.logger import logger
from src.models import Session
from src.config import ACTIVE, CREATED, WAITING_FOR_USER, PAUSED, COMPLETED, EXPIRED
from sqlalchemy import select


class GroupChatSessionManager:
    """群聊会话管理器"""

    def __init__(
        self,
        claude_session_manager: ClaudeSessionManager,
        session_repository: SessionRepository,
        feishu_client: FeishuClient
    ):
        self.claude_session_manager = claude_session_manager
        self.session_repository = session_repository
        self.feishu_client = feishu_client

    async def get_qa_session(self, event: GroupMessageEvent):
        """
        获取普通问答会话（临时会话，不保持上下文）

        Args:
            event: 群聊消息事件

        Returns:
            Claude会话客户端
        """
        # 每次普通问答都创建新会话键，不保持上下文
        session_key = f"{event.user_id}:qa:{event.chat_id}"

        logger.info(f"获取普通问答会话: session_key={session_key}")

        # 获取或创建会话
        claude_client = await self.claude_session_manager.get_or_create_session(
            session_key=session_key
        )

        # 更新会话记录，标记为群聊普通问答会话
        await self._update_session_info(
            session_key=session_key,
            session_type="group_qa",
            user_id=event.user_id,
            chat_id=event.chat_id,
            thread_id=None,
            requirement_id=None
        )

        return claude_client

    async def get_demand_session(
        self,
        requirement_id: str,
        thread_id: str,
        chat_id: str,
        user_id: str
    ):
        """
        获取需求会话（持久会话，保持话题内完整上下文）

        Args:
            requirement_id: 需求ID
            thread_id: 话题ID
            chat_id: 群ID
            user_id: 用户ID

        Returns:
            Claude会话客户端
        """
        # 需求会话键格式：{requirement_id}:{thread_id}
        session_key = f"{requirement_id}:{thread_id}"

        logger.info(f"获取需求会话: session_key={session_key}, requirement_id={requirement_id}")

        # 获取或创建会话
        claude_client = await self.claude_session_manager.get_or_create_session(
            session_key=session_key
        )

        # 更新会话记录，标记为需求话题会话
        await self._update_session_info(
            session_key=session_key,
            session_type="group_demand",
            user_id=user_id,
            chat_id=chat_id,
            thread_id=thread_id,
            requirement_id=requirement_id
        )

        return claude_client

    async def get_session_by_requirement(self, requirement_id: str, thread_id: str):
        """
        根据需求ID获取会话

        Args:
            requirement_id: 需求ID
            thread_id: 话题ID

        Returns:
            Claude会话客户端，不存在则返回None
        """
        session_key = f"{requirement_id}:{thread_id}"
        return await self.claude_session_manager.get_session(session_key)

    async def _update_session_info(
        self,
        session_key: str,
        session_type: str,
        user_id: str,
        chat_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        requirement_id: Optional[str] = None
    ) -> None:
        """
        更新会话信息

        Args:
            session_key: 会话键
            session_type: 会话类型
            user_id: 用户ID
            chat_id: 群ID
            thread_id: 话题ID
            requirement_id: 需求ID
        """
        try:
            async with AsyncSessionLocal() as db:
                # 获取或创建会话记录
                result = await db.execute(
                    select(Session).where(Session.session_key == session_key)
                )
                session = result.scalar_one_or_none()

                if session:
                    # 更新现有会话
                    session.session_type = session_type
                    session.chat_id = chat_id
                    session.thread_id = thread_id
                    session.requirement_id = requirement_id
                    session.updated_at = datetime.now()
                else:
                    # 创建新会话记录
                    session = Session(
                        session_key=session_key,
                        user_id=user_id,
                        root_id=thread_id or chat_id,
                        session_type=session_type,
                        chat_id=chat_id,
                        thread_id=thread_id,
                        requirement_id=requirement_id,
                        state=ACTIVE
                    )
                    db.add(session)

                await db.commit()
                logger.debug(f"会话信息已更新: session_key={session_key}, session_type={session_type}")

        except Exception as e:
            logger.error(f"更新会话信息失败: {e}", exc_info=True)

    async def cleanup_qa_session(self, event: GroupMessageEvent) -> None:
        """
        清理普通问答会话（临时会话，使用后可清理）

        Args:
            event: 群聊消息事件
        """
        # 普通问答会话是临时的，可以选择在对话结束后清理
        # 这里暂不实现自动清理，由会话管理器根据过期时间处理
        pass

    async def get_session_info(self, session_key: str) -> Optional[dict]:
        """
        获取会话信息

        Args:
            session_key: 会话键

        Returns:
            会话信息字典，不存在则返回None
        """
        session = await self.session_repository.get_by_key(session_key)
        if not session:
            return None

        return {
            "session_key": session.session_key,
            "session_type": session.session_type,
            "user_id": session.user_id,
            "chat_id": session.chat_id,
            "thread_id": session.thread_id,
            "requirement_id": session.requirement_id,
            "state": session.state.value if session.state else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }
