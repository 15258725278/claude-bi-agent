"""
需求检测器
"""
from typing import Optional
from datetime import datetime, timedelta
from src.config import settings, SessionState
from src.storage import SessionRepository


class DemandDetector:
    """需求检测器"""

    def __init__(self, session_repository: SessionRepository):
        self.session_repository = session_repository

    async def is_new_demand(
        self,
        user_id: str,
        current_message: str,
        session_key: str
    ) -> tuple[bool, str]:
        """
        判断是否为新需求

        Args:
            user_id: 用户ID
            current_message: 当前消息
            session_key: 当前会话键

        Returns:
            (is_new, reason): 是否为新需求及原因
        """

        # 1. 检查显式关键词
        for keyword in settings.NEW_DEMAND_KEYWORDS:
            if keyword in current_message.lower():
                return True, f"检测到关键词: {keyword}"

        # 2. 检查是否有等待回复的会话（优先级最高）
        # 由调用者检查，这里返回False
        # 3. 检查话题相似度（使用语义相似度）
        recent_sessions = await self.session_repository.get_user_sessions(user_id, limit=3)
        if recent_sessions:
            # 获取最近会话的摘要（简化实现：使用最后一条消息）
            last_session = recent_sessions[0]
            similarity = self._calculate_similarity(
                current_message,
                f"之前的会话话题: {last_session.session_key}"
            )
            if similarity < settings.CONTEXT_SIMILARITY_THRESHOLD:
                return True, f"话题相似度低: {similarity:.2f}"

            # 4. 检查时间间隔
            time_gap = (datetime.now() - last_session.updated_at).total_seconds()
            if time_gap > settings.TIME_GAP_THRESHOLD:
                return True, f"时间间隔过长: {int(time_gap)}秒"

        return False, "继续当前会话"

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 简单实现：可替换为BERT等语义模型
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0
