"""
消息分发器
"""
import asyncio
from typing import Optional
from src.core.session_manager import SessionManager
from src.core.handlers.message_handler import MessageHandler
from src.core.handlers.card_handler import CardHandler
from src.storage.redis_client import get_waiting_key
from src.storage import SessionRepository, WaitingContextRepository
from src.core.context import ContextManager
from src.feishu import FeishuClient
from src.config import settings


class MessageDispatcher:
    """消息分发器"""

    def __init__(
        self,
        session_manager: SessionManager,
        message_handler: MessageHandler,
        card_handler: CardHandler,
        feishu_client: FeishuClient
    ):
        self.session_manager = session_manager
        self.message_handler = message_handler
        self.card_handler = card_handler
        self.feishu_client = feishu_client

    async def dispatch(
        self,
        user_id: str,
        open_id: str,
        message_id: str,
        content: str,
        message: dict
    ) -> None:
        """
        分发用户消息（后台任务）

        Args:
            user_id: 用户ID
            open_id: 用户OpenID（用于发送消息，避免权限问题）
            message_id: 消息ID
            content: 消息内容
            message: 完整消息对象
        """
        try:
            # 处理用户消息
            error = await self.message_handler.handle_user_message(user_id, message)

            if error:
                # 发送错误提示给用户（使用 open_id）
                await self.feishu_client.send_message(
                    user_id=open_id,
                    content=f"抱歉，处理您的请求时出错了：{error}"
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.feishu_client.send_message(
                user_id=open_id,
                content=f"抱歉，系统出现错误，请稍后重试。"
            )

    async def dispatch_card_action(
        self,
        user_id: str,
        open_id: str,
        card_id: str,
        action_tag: Optional[str],
        form_values: Optional[dict]
    ) -> None:
        """
        分发卡片交互事件（后台任务）

        Args:
            user_id: 用户ID
            open_id: 用户OpenID（用于发送消息，避免权限问题）
            card_id: 卡片ID
            action_tag: 操作标签
            form_values: 表单值
        """
        try:
            # 处理卡片交互
            error = await self.card_handler.handle_card_action(
                user_id, card_id, action_tag, form_values
            )

            if error:
                await self.feishu_client.send_message(
                    user_id=open_id,
                    content=f"处理卡片交互失败：{error}"
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
