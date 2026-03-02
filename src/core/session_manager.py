"""
会话管理器
"""
import asyncio
import uuid
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from claude_agent_sdk import Message, AssistantMessage, ResultMessage, SystemMessage, TextBlock

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
        open_id: str,
        message_id: str,
        content: str,
        message: dict = None
    ) -> None:
        """
        分发消息处理

        Args:
            user_id: 用户ID（用于会话键）
            open_id: 用户OpenID（用于发送消息，避免权限问题）
            message_id: 消息ID
            content: 消息内容
            message: 完整消息对象（用于长连接）
        """
        from src.utils.logger import logger
        logger.info(f"[SessionManager] 开始处理消息: user_id={user_id}, content={content[:50]}...")
        try:
            # 生成会话键
            root_id = message.get("root_id") if message else message_id
            session_key = f"{user_id}:{root_id}"

            # 获取或创建 Claude 会话
            logger.info(f"[SessionManager] 获取或创建会话: session_key={session_key}")
            claude_client = await self.claude_session_manager.get_or_create_session(
                session_key=session_key
            )
            logger.info(f"[SessionManager] 会话已创建/获取，开始发送消息...")

            # 设置当前会话到工具管理器
            logger.info(f"[SessionManager] 设置当前会话键: session_key={session_key}")
            try:
                self.feishu_tools_manager.set_current_session_key(session_key)
                logger.info(f"[SessionManager] 会话键设置成功")
            except Exception as e:
                logger.error(f"[SessionManager] 设置会话键失败: {e}")
                raise

            # 立即发送确认表情（表示正在处理）
            try:
                await self.feishu_client.send_ack_emoji(user_id=open_id)
                logger.info(f"[SessionManager] 已发送确认表情")
            except Exception as e:
                logger.warning(f"[SessionManager] 发送确认表情失败: {e}")

            # 发送消息给 Claude
            logger.info(f"[SessionManager] 准备发送用户消息给 Claude...")
            # 注意：session_id 需要从选项中获取或从返回的 ResultMessage 中获取
            user_message = {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": content
                }
            }

            logger.info(f"[SessionManager] 用户消息创建完成，准备发送给 Claude...")

            # 发送消息给 Claude（使用 query 方法）
            logger.info(f"[SessionManager] 发送消息到 Claude...")
            await claude_client.query(content)
            logger.info(f"[SessionManager] 消息已发送，准备接收响应...")

            # 接收并处理响应
            logger.info(f"[SessionManager] 开始等待 Claude 响应...")
            msg_count = 0
            response_gen = claude_client.receive_response()
            logger.info(f"[SessionManager] 获取到响应生成器")
            async for msg in response_gen:
                msg_count += 1
                logger.info(f"[SessionManager] 收到消息 #{msg_count}: type={type(msg)}")
                await self._process_claude_message(
                    msg=msg,
                    user_id=open_id,  # 使用 open_id 发送消息，避免权限问题
                    session_key=session_key,
                    claude_client=claude_client,
                    feishu_client=self.feishu_client
                )

                # ResultMessage 表示响应完成
                if isinstance(msg, ResultMessage):
                    logger.info(f"[SessionManager] 收到 ResultMessage，结束循环")
                    break

            logger.info(f"[SessionManager] 响应处理完成，共收到 {msg_count} 条消息")
            # 标记会话为活跃
            await self.session_repository.update_state(session_key, SessionState.ACTIVE)

        except Exception as e:
            from src.utils.logger import logger
            logger.error(f"处理消息失败: {e}", exc_info=True)

    async def dispatch_card_action(
        self,
        user_id: str,
        open_id: str,
        card_id: str,
        action_tag: Optional[str] = None,
        form_values: dict = None
    ) -> None:
        """
        分发卡片动作

        Args:
            user_id: 用户ID（用于会话键）
            open_id: 用户OpenID（用于发送消息，避免权限问题）
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

            # 立即发送确认表情（表示正在处理）
            try:
                await self.feishu_client.send_ack_emoji(user_id=open_id)
                logger.info(f"[SessionManager] 已发送确认表情（卡片动作）")
            except Exception as e:
                logger.warning(f"[SessionManager] 发送确认表情失败: {e}")

            # 构建卡片事件消息
            card_action_desc = f"用户点击了 {action_tag}" if action_tag else "用户点击了卡片"
            content = f"卡片动作：{card_action_desc}。表单数据：{form_values}"

            logger.info(f"[SessionManager] 发送卡片动作消息到 Claude: {content[:50]}...")
            await claude_client.query(content)
            logger.info(f"[SessionManager] 卡片动作消息已发送，准备接收响应...")

            # 处理响应
            async for msg in claude_client.receive_response():
                await self._process_claude_message(
                    msg=msg,
                    user_id=open_id,  # 使用 open_id 发送消息，避免权限问题
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

                if isinstance(block, TextBlock):
                    # 发送文本到飞书
                    text = block.text
                    await feishu_client.send_message(user_id=user_id, content=text)
                    logger.info(f"发送回复给用户: {text[:100]}")

        # 处理工具调用结果
        elif isinstance(msg, ResultMessage):
            # 记录成本（如果有）
            if msg.total_cost_usd:
                logger.info(f"本次对话成本: ${msg.total_cost_usd:.4f}")

            # 记录使用情况
            if msg.usage:
                logger.info(f"使用情况: {msg.usage}")

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
