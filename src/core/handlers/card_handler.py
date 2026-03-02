"""
卡片处理器
"""
from typing import Optional
from src.storage.redis_client import get_waiting_key
from src.storage import SessionRepository, WaitingContextRepository
from src.core.context import ContextManager
from src.feishu import FeishuClient, CardBuilder
from src.config import SessionState


class CardHandler:
    """卡片处理器"""

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

    async def handle_card_action(
        self,
        user_id: str,
        card_id: str,
        action_tag: Optional[str],
        form_values: Optional[dict]
    ) -> Optional[str]:
        """
        处理卡片交互事件

        Returns:
            错误信息，无则成功
        """
        try:
            # 获取会话
            session = await self.session_repository.get_by_card_id(card_id)
            if not session:
                return f"未找到卡片对应的会话"

            # 检查会话状态
            if session.state == SessionState.EXPIRED:
                return "会话已过期"

            session_key = session.session_key

            # 获取Claude客户端
            claude_client = await self.session_manager.get_session(session_key)
            if not claude_client:
                return "Claude会话未找到"

            # 获取等待上下文
            waiting_context = await self.context_manager.get_waiting_context(session_key)

            if waiting_context:
                # 有等待上下文，用户回复了表单
                # 构建用户回复
                user_reply = self._build_form_reply(form_values)

                # 构建带上下文的查询
                query_content = await self.context_manager.build_context_query(
                    user_reply, waiting_context
                )

                # 清除等待上下文
                await self.context_manager.clear_waiting_context(session_key)

                # 发送给Claude
                await claude_client.query(query_content)

                # 接收响应
                async for message in claude_client.receive_response():
                    # 处理消息
                    pass

                # 更新卡片状态
                await self._update_card_status(session_key, "处理中", "正在处理您的补充信息...")

            return None

        except Exception as e:
            import traceback
            error_msg = f"处理卡片交互失败: {str(e)}"
            traceback.print_exc()
            return error_msg

    def _build_form_reply(self, form_values: dict) -> str:
        """构建表单回复字符串"""
        if not form_values:
            return ""

        parts = []
        for key, value in form_values.items():
            parts.append(f"{key}: {value}")

        return ", ".join(parts)

    async def _update_card_status(
        self,
        session_key: str,
        status: str,
        content: str,
        buttons: list = None
    ) -> None:
        """更新卡片状态"""
        # TODO: 实现卡片更新
        pass
