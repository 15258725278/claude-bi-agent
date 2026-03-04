"""
需求管理服务
"""
import uuid
from typing import Optional, Dict, List
from datetime import datetime
from sqlalchemy import select, update, and_
from src.storage import AsyncSessionLocal
from src.storage.memory_store import redis_client
from src.models import DataRequirement
from src.feishu import TopicService
from src.utils.logger import logger


class DemandStatus:
    """需求状态常量"""
    PENDING = "pending"                       # 待处理
    SCOPE_CONFIRMED = "scope_confirmed"       # 口径已确认
    ANALYZING = "analyzing"                   # 分析中
    WAITING_FEEDBACK = "waiting_feedback"     # 待反馈
    COMPLETED = "completed"                   # 已完成
    CANCELLED = "cancelled"                  # 已取消


class DemandPriority:
    """需求优先级常量"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DemandService:
    """需求管理服务"""

    def __init__(self, topic_service: TopicService):
        self.topic_service = topic_service

    async def create_demand(
        self,
        chat_id: str,
        title: str,
        description: str,
        created_by: str,
        created_by_name: Optional[str] = None,
        dimensions: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        priority: str = DemandPriority.NORMAL,
        root_message_id: Optional[str] = None
    ) -> DataRequirement:
        """
        创建需求

        Args:
            chat_id: 群ID
            title: 需求标题
            description: 需求描述
            created_by: 创建人user_id
            created_by_name: 创建人名称
            dimensions: 分析维度
            time_range: 时间范围
            priority: 优先级
            root_message_id: 原始消息ID（用于创建话题）

        Returns:
            创建的需求对象
        """
        logger.info(f"创建需求: title={title}, created_by={created_by}")

        try:
            # 生成需求ID
            requirement_id = f"req_{uuid.uuid4().hex[:12]}"

            # 创建话题（通过回复原始消息）
            if root_message_id:
                # 回复原始消息创建话题，发送简短确认消息
                # 不重复发送用户的需求描述，避免内容重复
                topic_info = await self.topic_service.create_topic(
                    root_message_id=root_message_id,
                    content="👌",
                    message_type="text"
                )
            else:
                # 如果没有原始消息ID，则记录警告（这种情况不应发生）
                logger.warning("创建需求时缺少 root_message_id，话题可能无法正常创建")
                topic_info = {
                    "root_id": None,
                    "thread_id": None,
                    "message_id": None,
                }

            # 创建需求记录
            async with AsyncSessionLocal() as db:
                demand = DataRequirement(
                    requirement_id=requirement_id,
                    title=title,
                    description=description,
                    dimensions=dimensions or [],
                    time_range=time_range,
                    priority=priority,
                    chat_id=chat_id,
                    thread_id=topic_info["thread_id"],
                    root_id=topic_info["root_id"],
                    status=DemandStatus.PENDING,
                    created_by=created_by,
                    created_by_name=created_by_name or created_by,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(demand)
                await db.commit()
                await db.refresh(demand)

            logger.info(f"需求创建成功: requirement_id={requirement_id}")
            return demand

        except Exception as e:
            logger.error(f"创建需求失败: {e}", exc_info=True)
            raise

    async def get_demand(self, requirement_id: str) -> Optional[DataRequirement]:
        """
        获取需求

        Args:
            requirement_id: 需求ID

        Returns:
            需求对象，不存在则返回None
        """
        async with AsyncSessionLocal() as db:
            stmt = select(DataRequirement).where(
                DataRequirement.requirement_id == requirement_id
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    async def get_demand_by_thread(self, thread_id: str) -> Optional[DataRequirement]:
        """
        通过话题ID获取需求

        Args:
            thread_id: 话题ID

        Returns:
            需求对象，不存在则返回None
        """
        async with AsyncSessionLocal() as db:
            stmt = select(DataRequirement).where(
                DataRequirement.thread_id == thread_id
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    async def get_demand_by_card(self, card_message_id: str) -> Optional[DataRequirement]:
        """
        通过卡片消息ID获取需求

        Args:
            card_message_id: 卡片消息ID

        Returns:
            需求对象，不存在则返回None
        """
        async with AsyncSessionLocal() as db:
            stmt = select(DataRequirement).where(
                DataRequirement.card_message_id == card_message_id
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    async def get_demand_by_card_token(self, card_token: str) -> Optional[DataRequirement]:
        """
        通过卡片token获取需求

        Args:
            card_token: 卡片token

        Returns:
            需求对象，不存在则返回None
        """
        async with AsyncSessionLocal() as db:
            stmt = select(DataRequirement).where(
                DataRequirement.card_token == card_token
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    async def update_demand_status(
        self,
        requirement_id: str,
        status: str
    ) -> DataRequirement:
        """
        更新需求状态

        Args:
            requirement_id: 需求ID
            status: 新状态

        Returns:
            更新后的需求对象
        """
        logger.info(f"更新需求状态: requirement_id={requirement_id}, status={status}")

        async with AsyncSessionLocal() as db:
            stmt = (
                update(DataRequirement)
                .where(DataRequirement.requirement_id == requirement_id)
                .values(status=status, updated_at=datetime.now())
            )
            await db.execute(stmt)
            await db.commit()

            # 获取更新后的需求
            return await self.get_demand(requirement_id)

    async def update_demand_fields(
        self,
        requirement_id: str,
        **kwargs
    ) -> DataRequirement:
        """
        更新需求字段

        Args:
            requirement_id: 需求ID
            **kwargs: 要更新的字段

        Returns:
            更新后的需求对象
        """
        logger.info(f"更新需求字段: requirement_id={requirement_id}, fields={list(kwargs.keys())}")

        async with AsyncSessionLocal() as db:
            stmt = (
                update(DataRequirement)
                .where(DataRequirement.requirement_id == requirement_id)
                .values(**kwargs, updated_at=datetime.now())
            )
            await db.execute(stmt)
            await db.commit()

            return await self.get_demand(requirement_id)

    async def update_card_info(
        self,
        requirement_id: str,
        card_message_id: str,
        card_token: Optional[str] = None
    ) -> DataRequirement:
        """
        更新需求卡片信息

        Args:
            requirement_id: 需求ID
            card_message_id: 卡片消息ID
            card_token: 卡片token

        Returns:
            更新后的需求对象
        """
        logger.info(f"更新需求卡片信息: requirement_id={requirement_id}, card_message_id={card_message_id}")

        return await self.update_demand_fields(
            requirement_id,
            card_message_id=card_message_id,
            card_token=card_token
        )

    async def set_analysis_result(
        self,
        requirement_id: str,
        analysis_result: Dict
    ) -> DataRequirement:
        """
        设置分析结果

        Args:
            requirement_id: 需求ID
            analysis_result: 分析结果

        Returns:
            更新后的需求对象
        """
        logger.info(f"设置分析结果: requirement_id={requirement_id}")

        return await self.update_demand_fields(
            requirement_id,
            analysis_result=analysis_result
        )

    async def set_feedback(
        self,
        requirement_id: str,
        feedback: str
    ) -> DataRequirement:
        """
        设置用户反馈

        Args:
            requirement_id: 需求ID
            feedback: 用户反馈

        Returns:
            更新后的需求对象
        """
        logger.info(f"设置用户反馈: requirement_id={requirement_id}")

        return await self.update_demand_fields(
            requirement_id,
            feedback=feedback
        )

    async def complete_demand(
        self,
        requirement_id: str
    ) -> DataRequirement:
        """
        完成需求

        Args:
            requirement_id: 需求ID

        Returns:
            更新后的需求对象
        """
        logger.info(f"完成需求: requirement_id={requirement_id}")

        async with AsyncSessionLocal() as db:
            stmt = (
                update(DataRequirement)
                .where(DataRequirement.requirement_id == requirement_id)
                .values(
                    status=DemandStatus.COMPLETED,
                    updated_at=datetime.now(),
                    completed_at=datetime.now()
                )
            )
            await db.execute(stmt)
            await db.commit()

            return await self.get_demand(requirement_id)

    async def cancel_demand(
        self,
        requirement_id: str
    ) -> DataRequirement:
        """
        取消需求

        Args:
            requirement_id: 需求ID

        Returns:
            更新后的需求对象
        """
        logger.info(f"取消需求: requirement_id={requirement_id}")

        return await self.update_demand_status(
            requirement_id,
            DemandStatus.CANCELLED
        )

    async def list_demands(
        self,
        chat_id: Optional[str] = None,
        status: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 50
    ) -> List[DataRequirement]:
        """
        获取需求列表

        Args:
            chat_id: 群ID（可选）
            status: 状态（可选）
            created_by: 创建人（可选）
            limit: 限制数量

        Returns:
            需求列表
        """
        async with AsyncSessionLocal() as db:
            conditions = []
            if chat_id:
                conditions.append(DataRequirement.chat_id == chat_id)
            if status:
                conditions.append(DataRequirement.status == status)
            if created_by:
                conditions.append(DataRequirement.created_by == created_by)

            stmt = (
                select(DataRequirement)
                .where(and_(*conditions) if conditions else True)
                .order_by(DataRequirement.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())

    # ========== 临时卡片上下文存储 ==========

    async def save_card_context(
        self,
        card_token: str,
        chat_id: str,
        root_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        保存卡片上下文（用于临时存储提交卡片的上下文）

        Args:
            card_token: 卡片token
            chat_id: 群ID
            root_id: 话题根消息ID
            user_id: 用户ID
        """
        try:
            import json
            key = f"card_context:{card_token}"
            context = {
                "chat_id": chat_id,
                "root_id": root_id,
                "user_id": user_id
            }
            await redis_client.setex(key, json.dumps(context), 3600)  # 1小时过期
            logger.debug(f"卡片上下文已保存: card_token={card_token}")
        except Exception as e:
            logger.warning(f"保存卡片上下文失败: {e}")

    async def get_card_context(
        self,
        card_token: str
    ) -> Optional[Dict]:
        """
        获取卡片上下文

        Args:
            card_token: 卡片token

        Returns:
            卡片上下文字典，不存在则返回None
        """
        try:
            import json
            key = f"card_context:{card_token}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"获取卡片上下文失败: {e}")
            return None

    async def delete_card_context(
        self,
        card_token: str
    ) -> None:
        """
        删除卡片上下文

        Args:
            card_token: 卡片token
        """
        try:
            key = f"card_context:{card_token}"
            await redis_client.delete(key)
            logger.debug(f"卡片上下文已删除: card_token={card_token}")
        except Exception as e:
            logger.warning(f"删除卡片上下文失败: {e}")

    # ========== 等待需求内容状态 ==========

    async def set_waiting_demand(
        self,
        chat_id: str,
        user_id: str
    ) -> None:
        """
        设置等待需求内容状态

        Args:
            chat_id: 群ID
            user_id: 用户ID
        """
        try:
            import json
            key = f"waiting_demand:{chat_id}:{user_id}"
            context = {
                "chat_id": chat_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            await redis_client.setex(key, json.dumps(context), 300)  # 5分钟过期
            logger.debug(f"等待需求状态已设置: chat_id={chat_id}, user_id={user_id}")
        except Exception as e:
            logger.warning(f"设置等待需求状态失败: {e}")

    async def get_waiting_demand(
        self,
        chat_id: str,
        user_id: str
    ) -> Optional[Dict]:
        """
        获取等待需求状态

        Args:
            chat_id: 群ID
            user_id: 用户ID

        Returns:
            等待状态字典，不存在则返回None
        """
        try:
            import json
            key = f"waiting_demand:{chat_id}:{user_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"获取等待需求状态失败: {e}")
            return None

    async def delete_waiting_demand(
        self,
        chat_id: str,
        user_id: str
    ) -> None:
        """
        删除等待需求状态

        Args:
            chat_id: 群ID
            user_id: 用户ID
        """
        try:
            key = f"waiting_demand:{chat_id}:{user_id}"
            await redis_client.delete(key)
            logger.debug(f"等待需求状态已删除: chat_id={chat_id}, user_id={user_id}")
        except Exception as e:
            logger.warning(f"删除等待需求状态失败: {e}")
