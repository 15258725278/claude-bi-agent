"""
消息处理器
"""
from typing import Optional
from src.config import settings, SessionState
from src.core.session_manager import SessionManager
from src.core.handlers.claude_handler import ClaudeHandler
from src.core.context import ContextManager
from src.storage.redis_client import get_waiting_key
from src.feishu import FeishuClient
from src.storage import SessionRepository, WaitingContextRepository


class MessageHandler:
    """消息处理器"""

    def __init__(
        self,
        session_manager: SessionManager,
        claude_handler: ClaudeHandler,
        feishu_client: FeishuClient,
        session_repository: SessionRepository,
        waiting_repository: WaitingContextRepository,
        context_manager: ContextManager
    ):
        self.session_manager = session_manager
        self.claude_handler = claude_handler
        self.feishu_client = feishu_client
        self.session_repository = session_repository
        self.waiting_repository = waiting_repository
        self.context_manager = context_manager

    async def handle_user_message(
        self,
        user_id: str,
        message: dict
    ) -> Optional[str]:
        """
        处理用户消息

        Returns:
            错误信息，无则成功
        """
        try:
            # 提取消息内容
            content = self._extract_text(message)
            if not content:
                return None

            # 获取或创建会话
            session, is_new, error = await self.session_manager.get_or_create_session(
                user_id, message
            )

            if error:
                return error

            if not session:
                return "会话获取失败"

            session_key = session.session_key

            # 获取Claude客户端实例
            claude_client = await self.session_manager.get_session(session_key)
            if not claude_client:
                # 检查会话是否过期
                session_db = await self.session_repository.get_by_key(session_key)
                if session_db and session_db.state == SessionState.EXPIRED:
                    return "会话已过期，请重新发起"

                return "Claude会话�失败"

            # 处理消息
            error = await self.claude_handler.process_message(
                session_key, claude_client, content
            )

            return error

        except Exception as e:
            import traceback
            error_msg = f"处理消息失败: {str(e)}"
            traceback.print_exc()
            return error_msg

    def _extract_text(self, message: dict) -> str:
        """提取消息文本"""
        content = message.get("content", "{}")
        try:
            import json
            content_dict = json.loads(content)
            text = content_dict.get("text", "")
            # 去除@mention
            import re
            text = re.sub(r'<at[^>]*>', '', text)
            text = re.sub(r'</at>', '', text)
            return text.strip()
        except:
            return ""
