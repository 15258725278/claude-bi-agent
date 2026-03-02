"""
会话管理器
"""
import asyncio
import uuid
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from claude_agent_sdk import Message, AssistantMessage, ResultMessage, SystemMessage

from src.config import settings, SessionState
from src.models import Session, WaitingContext
from src.storage import (
    SessionRepository,
    WaitingContextRepository,
    redis_client,
    get_session_key,
    get_waiting_key,
)
from src.claude import ClaudeSessionManager, FeishuToolsManager
from src.feishu import FeishuClient
from src.core.demand_detector import DemandDetector
from src.core.context import ContextManager


class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        session_repository: SessionRepository,
        waiting_repository: WaitingContextRepository,
        feishu_client: FeishuClient,
        claude_session_manager: ClaudeSessionManager,
        feishu_tools_manager: FeishuToolsManager,
    ):
        self.session_repository = session_repository
        self.waiting_repository = waiting_repository
        self.feishu_client = feishu_client
        self.claude_session_manager = claude_session_manager
        self.feishu_tools_manager = feishu_tools_manager
        self.demand_detector = DemandDetector(session_repository)
        self.context_manager = ContextManager()

    async def dispatch(
        self,
        user_id: str,
        message_id: str,
        content: str,
        message: dict = None
    ) -> None:
        """
        分发消息处理

        Args:
            user_id: 用户ID
            message_id: 消息ID
            content: 消息内容
            message: 完整消息对象（用于长连接）
        """
        try:
            # 生成会话键
            root_id = message.get("root_id") if message else message_id
            session_key = f"{user_id}:{root_id}"

            # 获取或创建 Claude 会话
            claude_client = await self.claude_session_manager.get_or_create_session(
                session_key=session_key
            )

            # 设置当前会话到工具管理器
            self.feishu_tools_manager.set_current_session_key(session_key)

            # 发送消息给 Claude
            user_message = {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": content
                },
                "session_id": claude_client.claude_session_id
            }

            # 接收并处理响应
            async for msg in claude_client.client.receive_response():
                await self._process_claude_message(
                    msg=msg,
                    user_id=user_id,
                    session_key=session_key,
                    claude_client=claude_client,
                    feishu_client=self.feishu_client
                )

                # ResultMessage 表示响应完成
                if isinstance(msg, ResultMessage):
                    break

            # 标记会话为活跃
            await self.session_repository.update_state(session_key, SessionState.ACTIVE)

        except Exception as e:
            from src.utils.logger import logger
            logger.error(f"处理消息失败: {e}", exc_info=True)

    async def dispatch_card_action(
        self,
        user_id: str,
        card_id: str,
        action_tag: Optional[str] = None,
        form_values: dict = None
    ) -> None:
        """
        分发卡片动作

        Args:
            user_id: 用户ID
            card_id: 卡片ID
            action_tag: 动作标签
            form_values: 表单数据
        """
        try:
            # 查找对应会话
            session = await self.session_repository.get_by_card_id(card_id)
            if not session:
                from src.utils.logger import logger
                logger.warning(f"未找到卡片 {card_id} 对应的会话")
                return

            session_key = session.session_key

            # 获取 Claude 会话
            claude_client = await self.claude_session_manager.get_or_create_session(
                session_key=session_key
            )

            # 构建卡片事件消息
            card_action_desc = f"用户点击了 {action_tag}" if action_tag else "用户点击了卡片"
            user_message = {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": f"卡片动作：{card_action_desc}。表单数据：{form_values}"
                },
                "session_id": claude_client.claude_session_id
            }

            # 处理响应
            async for msg in claude_client.client.receive_response():
                await self._process_claude_message(
                    msg=msg,
                    user_id=user_id,
                    session_key=session_key,
                    claude_client=claude_client,
                    feishu_client=self.feishu_client
                )

                if isinstance(msg, ResultMessage):
                    break

        except Exception as e:
            from src.utils.logger import logger
            logger.error(f"处理卡片动作失败: {e}", exc_info=True)

    async def _process_claude_message(
        self,
        msg: Message,
        user_id: str,
        session_key: str,
        claude_client,
        feishu_client: FeishuClient,
    ) -> None:
        """
        处理 Claude 消息

        Args:
            msg: Claude 消息
            user_id: 用户ID
            session_key: 会话键
            claude_client: Claude 会话客户端
            feishu_client: 飞书客户端
        """
        from src.utils.logger import logger

        # 处理文本消息
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, SystemMessage):
                    # 系统消息，忽略
                    logger.debug(f"系统消息: {block.data}")
                    continue

                if isinstance(block, str):
                    # 发送文本到飞书
                    await feishu_client.send_message(user_id=user_id, content=block)
                    logger.info(f"发送回复给用户: {block[:100]}")

        # 处理工具调用结果
        elif isinstance(msg, ResultMessage):
            if msg.error:
                logger.error(f"Claude 错误: {msg.error}")
                await feishu_client.send_message(
                    user_id=user_id,
                    content=f"抱歉，处理时发生了错误：{msg.error}"
                )
            else:
                # 记录成本（如果有）
                if msg.total_cost_usd:
                    logger.info(f"本次对话成本: ${msg.total_cost_usd:.4f}")

                # 标记会话完成
                await self.session_repository.update_state(session_key, SessionState.COMPLETED)

    async def get_session_info(self, session_key: str) -> Optional[dict]:
        """获取会话信息"""
        session = await self.session_repository.get_by_key(session_key)
        if not session:
            return None
        return {
            "session_key": session.session_key,
            "state": session.state,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
