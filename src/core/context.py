"""
上下文管理
"""
from datetime import datetime, timedelta
from typing import Optional
from src.models.session import WaitingContext
from src.config import settings


class ContextManager:
    """上下文管理器"""

    async def save_waiting_context(
        self,
        session_key: str,
        pending_question: str,
        conversation_summary: str = "",
        additional_data: dict = None
    ) -> None:
        """保存等待上下文"""
        context = WaitingContext(
            pending_question=pending_question,
            conversation_summary=conversation_summary,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=settings.REDIS_CACHE_TTL),
            additional_data=additional_data or {}
        )

        from src.storage.redis_client import redis_client, get_waiting_key
        redis_key = get_waiting_key(session_key)
        await redis_client.setex(redis_key, context.to_json(), settings.REDIS_CACHE_TTL)

    async def get_waiting_context(
        self,
        session_key: str
    ) -> Optional[WaitingContext]:
        """获取等待上下文"""
        from src.storage.redis_client import redis_client, get_waiting_key
        redis_key = get_waiting_key(session_key)
        data = await redis_client.get(redis_key)
        if data:
            return WaitingContext.from_json(data)
        return None

    async def clear_waiting_context(self, session_key: str) -> bool:
        """清除等待上下文"""
        from src.storage.redis_client import redis_client, get_waiting_key
        redis_key = get_waiting_key(session_key)
        return await redis_client.delete(redis_key)

    async def build_context_query(
        self,
        user_message: str,
        waiting_context: WaitingContext
    ) -> str:
        """
        构建带上下文的查询内容

        Args:
            user_message: 用户消息
            waiting_context: 等待上下文

        Returns:
            构建后的查询内容
        """
        query = f"""
            之前的对话：
            Claude: {waiting_context.pending_question}

            用户回复：{user_message}

            请根据用户的回复继续完成之前的任务。
            """

        return query.strip()

    def _build_conversation_summary(self, messages: list) -> str:
        """构建对话摘要"""
        # 简单实现：返回最后一条消息
        if messages:
            return messages[-1].get("content", "")
        return ""
