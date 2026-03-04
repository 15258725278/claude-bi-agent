"""
飞书话题服务
"""
from typing import Optional, Dict, List
from datetime import datetime
from src.feishu.client import FeishuClient
from src.models import ThreadMessage
from src.storage import AsyncSessionLocal
from sqlalchemy import select
from src.utils.logger import logger


class TopicService:
    """飞书话题服务"""

    def __init__(self, feishu_client: FeishuClient):
        self.feishu_client = feishu_client

    async def create_topic(
        self,
        root_message_id: str,
        content: str,
        message_type: str = "text"
    ) -> Dict[str, str]:
        """
        通过回复消息创建话题

        根据飞书官方文档，使用回复消息接口并设置 reply_in_thread=True 来创建话题。
        回复的那条消息的 message_id 就是话题的 root_id 和 thread_id。

        Args:
            root_message_id: 要回复的消息ID（即用户@机器人的那条消息）
            content: 回复内容
            message_type: 消息类型（text/interactive等）

        Returns:
            话题信息字典（包含root_id, thread_id, message_id）
        """
        logger.info(f"创建话题: root_message_id={root_message_id}")

        try:
            topic_info = await self.feishu_client.create_thread_by_reply(
                message_id=root_message_id,
                content=content,
                message_type=message_type
            )

            logger.info(f"话题创建成功: thread_id={topic_info['thread_id']}, root_id={topic_info['root_id']}")
            return topic_info

        except Exception as e:
            logger.error(f"创建话题失败: {e}", exc_info=True)
            raise

    async def send_message_to_topic(
        self,
        chat_id: str,
        root_id: str,
        content: str,
        message_type: str = "text",
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> Dict:
        """
        发送消息到话题

        Args:
            chat_id: 群ID
            root_id: 话题根消息ID
            content: 消息内容
            message_type: 消息类型
            sender_id: 发送者ID
            sender_name: 发送者名称

        Returns:
            消息响应数据
        """
        logger.debug(f"发送消息到话题: chat_id={chat_id}, root_id={root_id}, content={content[:50]}")

        try:
            response = await self.feishu_client.send_group_message(
                chat_id=chat_id,
                content=content,
                message_type=message_type,
                root_id=root_id
            )

            # 记录消息到数据库
            if sender_id:
                await self._save_thread_message(
                    message_id=response.message_id,
                    thread_id=root_id,  # 飞书中thread_id = root_id
                    root_id=root_id,
                    content=content,
                    message_type=message_type,
                    sender_id=sender_id,
                    sender_name=sender_name
                )

            return response

        except Exception as e:
            logger.error(f"发送消息到话题失败: {e}", exc_info=True)
            raise

    async def send_card_to_topic(
        self,
        chat_id: str,
        root_id: str,
        card: Dict,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> Dict:
        """
        发送卡片到话题

        Args:
            chat_id: 群ID
            root_id: 话题根消息ID
            card: 卡片内容（JSON格式）
            sender_id: 发送者ID
            sender_name: 发送者名称

        Returns:
            消息响应数据
        """
        logger.debug(f"发送卡片到话题: chat_id={chat_id}, root_id={root_id}")

        try:
            response = await self.feishu_client.send_card_to_thread(
                chat_id=chat_id,
                root_id=root_id,
                card=card
            )

            # 记录消息到数据库
            if sender_id:
                await self._save_thread_message(
                    message_id=response.message_id,
                    thread_id=root_id,
                    root_id=root_id,
                    content=str(card),
                    message_type="card",
                    sender_id=sender_id,
                    sender_name=sender_name
                )

            return response

        except Exception as e:
            logger.error(f"发送卡片到话题失败: {e}", exc_info=True)
            raise

    async def update_card_in_topic(
        self,
        message_id: str,
        card: Dict
    ) -> Dict:
        """
        更新话题中的卡片

        Args:
            message_id: 卡片消息ID
            card: 新的卡片内容（JSON格式）

        Returns:
            更新响应数据
        """
        logger.debug(f"更新话题中的卡片: message_id={message_id}")

        try:
            response = await self.feishu_client.update_card_by_message(
                message_id=message_id,
                card=card
            )

            return response

        except Exception as e:
            logger.error(f"更新卡片失败: {e}", exc_info=True)
            raise

    async def get_topic_messages(
        self,
        thread_id: str,
        limit: int = 50
    ) -> List[ThreadMessage]:
        """
        获取话题消息列表

        Args:
            thread_id: 话题ID
            limit: 限制数量

        Returns:
            消息列表
        """
        logger.debug(f"获取话题消息: thread_id={thread_id}, limit={limit}")

        async with AsyncSessionLocal() as db:
            stmt = (
                select(ThreadMessage)
                .where(ThreadMessage.thread_id == thread_id)
                .order_by(ThreadMessage.created_at)
                .limit(limit)
            )
            result = await db.execute(stmt)
            messages = result.scalars().all()
            return list(messages)

    async def _save_thread_message(
        self,
        message_id: str,
        thread_id: str,
        root_id: str,
        content: str,
        message_type: str,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> None:
        """
        保存话题消息到数据库

        Args:
            message_id: 消息ID
            thread_id: 话题ID
            root_id: 根消息ID
            content: 消息内容
            message_type: 消息类型
            sender_id: 发送者ID
            sender_name: 发送者名称
        """
        try:
            async with AsyncSessionLocal() as db:
                message = ThreadMessage(
                    message_id=message_id,
                    thread_id=thread_id,
                    root_id=root_id,
                    content=content,
                    message_type=message_type,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    created_at=datetime.now()
                )
                db.add(message)
                await db.commit()
                logger.debug(f"话题消息已保存: message_id={message_id}")

        except Exception as e:
            logger.error(f"保存话题消息失败: {e}", exc_info=True)
