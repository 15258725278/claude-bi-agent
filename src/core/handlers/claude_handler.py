"""
Claude消息处理器
"""
from typing import Optional
from claude_agent_sdk import Message, AssistantMessage, ResultMessage

from src.config import SessionState
from src.storage.redis_client import get_waiting_key, redis_client
from src.storage import SessionRepository, WaitingContextRepository
from src.feishu import FeishuClient
from src.core.context import ContextManager


class ClaudeHandler:
    """Claude处理器"""

    def __init__(
        self,
        feishu_client: FeishuClient,
        session_repository: SessionRepository,
        waiting_repository: WaitingContextRepository,
        context_manager: ContextManager
    ):
        self.feishu_client = feishu_client
        self.session_repository = session_repository
        self.waiting_repository = waiting_repository
        self.context_manager = context_manager

    async def process_message(
        self,
        session_key: str,
        claude_client,
        user_message: str
    ) -> Optional[str]:
        """
        处理用户消息

        Returns:
            错误信息，无则成功
        """
        try:
            # 构建查询内容（检查是否有等待上下文）
            waiting_context = await self.context_manager.get_waiting_context(session_key)
            query_content = user_message

            if waiting_context:
                # 有等待上下文，组合成连续对话
                query_content = await self.context_manager.build_context_query(
                    user_message, waiting_context
                )
                # 清除等待上下文
                await self.context_manager.clear_waiting_context(session_key)

            # 发送给Claude
            await claude_client.query(query_content)

            # 接收响应
            async for message in claude_client.receive_response():
                error = await self._handle_message(session_key, message)
                if error:
                    return error

            # 保存Claude session_id
            claude_session_id = claude_client.claude_session_id
            if claude_session_id:
                await self.session_repository.save_claude_session_id(session_key, claude_session_id)

            return None

        except Exception as e:
            return f"Claude处理失败: {str(e)}"

    async def _handle_message(
        self,
        session_key: str,
        message: Message
    ) -> Optional[str]:
        """处理单条Claude消息"""
        try:
            if isinstance(message, AssistantMessage):
                await self._handle_assistant_message(session_key, message)

            elif isinstance(message, ResultMessage):
                await self._handle_result_message(session_key, message)

            return None

        except Exception as e:
            return f"消息处理失败: {str(e)}"

    async def _handle_assistant_message(
        self,
        session_key: str,
        message: AssistantMessage
    ) -> None:
        """处理助手消息"""
        user_id = session_key.split(":")[0]

        # 检查消息内容
        for content in message.content:
            # 文本内容
            if hasattr(content, 'text'):
                await self.feishu_client.send_message(
                    user_id=user_id,
                    content=content.text
                )

            # 工具调用（已在工具内部处理，这里只需记录）
            if hasattr(content, 'name'):
                # 工具调用会自动处理
                pass

    async def _handle_result_message(
        self,
        session_key: str,
        message: ResultMessage
    ) -> None:
        """处理结果消息"""
        # 保存Claude session_id
        if hasattr(message, 'session_id'):
            await self.session_repository.save_claude_session_id(
                session_key, message.session_id
            )

        # 会话完成（注意：这里不自动标记完成，由业务层决定）
        # 如果没有等待上下文，可以标记为完成
        waiting_exists = await self.waiting_repository.exists(session_key)
        if not waiting_exists:
            # 更新会话状态
            await self.session_repository.update_state(
                session_key, SessionState.COMPLETED
            )
