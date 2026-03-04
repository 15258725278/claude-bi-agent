"""
群聊消息处理器
"""
from typing import Dict, Optional
import json
import re
from claude_agent_sdk import AssistantMessage, SystemMessage, TextBlock
from src.core.group_chat_router import GroupChatRouter, GroupMessageEvent, GroupMessageMode
from src.core.group_chat_session_manager import GroupChatSessionManager
from src.core.demand_service import DemandService, DemandStatus
from src.feishu import TopicService, DemandCardBuilder
from src.feishu.client import FeishuClient
from src.storage import SessionRepository
from src.claude import ClaudeSessionManager
from src.utils.logger import logger


class GroupChatHandler:
    """群聊消息处理器"""

    def __init__(
        self,
        feishu_client: FeishuClient,
        topic_service: TopicService,
        demand_service: DemandService,
        group_chat_session_manager: GroupChatSessionManager,
        claude_session_manager: ClaudeSessionManager,
        session_repository: SessionRepository
    ):
        self.feishu_client = feishu_client
        self.topic_service = topic_service
        self.demand_service = demand_service
        self.group_chat_session_manager = group_chat_session_manager
        self.claude_session_manager = claude_session_manager
        self.session_repository = session_repository
        self.router = GroupChatRouter()

    async def handle_group_message(self, event: dict) -> Dict:
        """
        处理群聊消息

        Args:
            event: 飞书事件对象

        Returns:
            处理结果
        """
        # 解析群聊消息事件
        group_event = self.router.parse_message_event(event)

        if not group_event:
            logger.info("不是群聊消息或无法解析，忽略")
            return {"status": "ignored", "reason": "not_group_message"}

        # 优先检查：如果消息在话题中，直接处理（不需要@机器人）
        if group_event.thread_id:
            demand = await self.demand_service.get_demand_by_thread(group_event.thread_id)
            if demand:
                logger.info(f"消息在需求话题中，直接处理: thread_id={group_event.thread_id}, requirement_id={demand.requirement_id}")
                # 话题内的消息直接路由到需求模式
                return await self._handle_demand_mode(group_event)

        # 检查是否有等待中的需求（用户正在回复需求内容）
        waiting = await self.demand_service.get_waiting_demand(group_event.chat_id, group_event.user_id)
        if waiting:
            logger.info(f"检测到等待中的需求，直接处理（无需@机器人）")
            return await self._handle_demand_mode(group_event)

        # 不在话题中且没有等待中的需求，需要@机器人
        if not group_event.mentions_bot:
            logger.info("未@机器人且不在话题中，忽略消息")
            return {"status": "ignored", "reason": "not_mentioned_bot"}

        # 路由消息到对应处理模式
        mode = self.router.route_message(group_event)

        logger.info(f"群聊消息路由: mode={mode.mode}, chat_id={group_event.chat_id}")

        if mode.mode == "demand":
            return await self._handle_demand_mode(group_event)
        else:
            return await self._handle_qa_mode(group_event)

    async def _handle_demand_mode(self, event: GroupMessageEvent) -> Dict:
        """
        处理需求管理模式

        Args:
            event: 群聊消息事件

        Returns:
            处理结果
        """
        logger.info(f"处理需求管理模式: user_id={event.user_id}, content={event.content}")

        try:
            # 如果消息在话题中，获取对应的需求
            if event.thread_id:
                demand = await self.demand_service.get_demand_by_thread(event.thread_id)

                if demand:
                    # 需求已存在，在话题中继续对话
                    logger.info(f"找到现有需求: requirement_id={demand.requirement_id}")
                    return await self._continue_demand_conversation(event, demand)

            # 检查是否有等待中的需求
            waiting = await self.demand_service.get_waiting_demand(event.chat_id, event.user_id)

            if waiting and "帮我处理需求" not in event.content:
                # 用户回复了需求内容，创建需求并处理
                logger.info(f"收到用户需求内容: {event.content[:100]}")
                await self.demand_service.delete_waiting_demand(event.chat_id, event.user_id)

                # 去除@其他用户的内容
                clean_content = self._clean_mentions(event.content)
                logger.info(f"清理后的需求内容: {clean_content[:100]}")

                # 直接使用用户回复的消息ID来创建话题
                root_message_id = event.message_id

                # 创建需求
                demand = await self.demand_service.create_demand(
                    chat_id=event.chat_id,
                    title=clean_content[:50] + "..." if len(clean_content) > 50 else clean_content,
                    description=clean_content,
                    created_by=event.user_id,
                    created_by_name=event.user_id,
                    dimensions=[],
                    time_range="",
                    priority="normal",
                    root_message_id=root_message_id
                )

                # 获取需求会话
                claude_client = await self.group_chat_session_manager.get_demand_session(
                    requirement_id=demand.requirement_id,
                    thread_id=demand.thread_id,
                    chat_id=demand.chat_id,
                    user_id=event.user_id
                )

                # 不需要发送额外确认表情，创建话题时已经发送了👌
                # await self.feishu_client.send_group_ack_emoji(...)

                # 发送消息给Claude
                await claude_client.query(clean_content)

                # 处理响应
                response_text = ""
                try:
                    async for msg in claude_client.receive_response():
                        # 只处理 AssistantMessage，过滤 SystemMessage
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    response_text += block.text + "\n"
                                # 跳过 SystemMessage，避免返回技能描述内容
                                elif isinstance(block, SystemMessage):
                                    continue

                        if msg.__class__.__name__ == 'ResultMessage':
                            logger.info(f"收到ResultMessage，结束接收")
                            break
                except Exception as e:
                    logger.error(f"接收Claude响应失败: {e}", exc_info=True)

                logger.info(f"Claude响应: {response_text[:200] if response_text else '(空)'}")

                # 发送回复到话题
                if response_text.strip():
                    await self.topic_service.send_message_to_topic(
                        chat_id=event.chat_id,
                        root_id=demand.root_id,
                        content=response_text.strip(),
                        sender_id="bot",
                        sender_name="AI助手"
                    )

                return {
                    "status": "demand_created_and_processed",
                    "requirement_id": demand.requirement_id
                }

            # 检查是否是需求触发关键词
            if "帮我处理需求" in event.content:
                # 发送需求提交引导消息
                card = DemandCardBuilder.build_demand_submit_card()

                # 发送到群聊
                await self.feishu_client.send_group_message(
                    chat_id=event.chat_id,
                    content=json.dumps(card),
                    message_type="interactive"
                )

                # 设置等待状态
                await self.demand_service.set_waiting_demand(
                    chat_id=event.chat_id,
                    user_id=event.user_id
                )

                return {
                    "status": "waiting",
                    "message": "已发送引导消息，等待用户输入需求内容"
                }

            return {"status": "ok"}

        except Exception as e:
            logger.error(f"处理需求管理模式失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _handle_qa_mode(self, event: GroupMessageEvent) -> Dict:
        """
        处理普通问答模式

        Args:
            event: 群聊消息事件

        Returns:
            处理结果
        """
        logger.info(f"处理普通问答模式: user_id={event.user_id}, content={event.content}")

        try:
            # 清除可能的等待需求状态（用户发送普通问答而不是需求）
            waiting = await self.demand_service.get_waiting_demand(event.chat_id, event.user_id)
            if waiting:
                await self.demand_service.delete_waiting_demand(event.chat_id, event.user_id)
                logger.info(f"清除等待需求状态: user_id={event.user_id}")

            # 获取普通问答会话（临时会话）
            claude_client = await self.group_chat_session_manager.get_qa_session(event)

            # 发送确认表情
            try:
                await self.feishu_client.send_group_ack_emoji(event.chat_id)
            except Exception as e:
                logger.warning(f"发送确认表情失败: {e}")

            # 提取实际问题内容（去除@机器人部分）
            content = self._extract_question(event.content)

            # 发送消息给Claude
            await claude_client.query(content)

            # 处理响应
            response_text = ""
            try:
                async for msg in claude_client.receive_response():
                    # 只处理 AssistantMessage，过滤 SystemMessage
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                response_text += block.text + "\n"
                            # 跳过 SystemMessage，避免返回技能描述内容
                            elif isinstance(block, SystemMessage):
                                continue

                    if msg.__class__.__name__ == 'ResultMessage':
                        logger.info(f"收到ResultMessage，结束接收")
                        break
            except Exception as e:
                logger.error(f"接收Claude响应失败: {e}", exc_info=True)

            logger.info(f"QA模式响应: {response_text[:200] if response_text else '(空)'}")

            # 发送回复到群聊
            if response_text.strip():
                await self.feishu_client.send_group_message(
                    chat_id=event.chat_id,
                    content=response_text.strip()
                )

            return {"status": "ok", "response": response_text}

        except Exception as e:
            logger.error(f"处理普通问答模式失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _continue_demand_conversation(
        self,
        event: GroupMessageEvent,
        demand
    ) -> Dict:
        """
        继续需求对话

        Args:
            event: 群聊消息事件
            demand: 需求对象

        Returns:
            处理结果
        """
        logger.info(f"继续需求对话: requirement_id={demand.requirement_id}")

        try:
            # 获取需求会话
            claude_client = await self.group_chat_session_manager.get_demand_session(
                requirement_id=demand.requirement_id,
                thread_id=demand.thread_id,
                chat_id=demand.chat_id,
                user_id=event.user_id
            )

            # 发送确认表情
            try:
                await self.feishu_client.send_group_ack_emoji(
                    chat_id=event.chat_id,
                    root_id=demand.root_id
                )
            except Exception as e:
                logger.warning(f"发送确认表情失败: {e}")

            # 发送消息给Claude
            await claude_client.query(event.content)

            # 处理响应
            response_text = ""
            try:
                async for msg in claude_client.receive_response():
                    # 只处理 AssistantMessage，过滤 SystemMessage
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                response_text += block.text + "\n"
                            # 跳过 SystemMessage，避免返回技能描述内容
                            elif isinstance(block, SystemMessage):
                                continue

                    if msg.__class__.__name__ == 'ResultMessage':
                        logger.info(f"收到ResultMessage，结束接收")
                        break
            except Exception as e:
                logger.error(f"接收Claude响应失败: {e}", exc_info=True)

            logger.info(f"继续需求对话响应: {response_text[:200] if response_text else '(空)'}")

            # 发送回复到话题
            if response_text.strip():
                await self.topic_service.send_message_to_topic(
                    chat_id=event.chat_id,
                    root_id=demand.root_id,
                    content=response_text.strip(),
                    sender_id="bot",
                    sender_name="AI助手"
                )

            return {"status": "ok", "response": response_text}

        except Exception as e:
            logger.error(f"继续需求对话失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def handle_demand_card_action(
        self,
        user_id: str,
        open_id: str,
        card_id: str,
        action_tag: str,
        form_values: dict,
        raw_event: dict
    ) -> Dict:
        """
        处理需求卡片动作

        Args:
            user_id: 用户ID
            open_id: 用户OpenID
            card_id: 卡片ID
            action_tag: 动作标签
            form_values: 表单数据
            raw_event: 原始事件

        Returns:
            处理结果
        """
        logger.info(f"处理需求卡片动作: action_tag={action_tag}, card_id={card_id}")

        try:
            # 根据动作标签处理
            if action_tag == "submit_demand":
                return await self._handle_submit_demand(user_id, open_id, form_values, raw_event)
            elif action_tag == "confirm_scope":
                return await self._handle_confirm_scope(card_id, raw_event)
            elif action_tag == "confirm_result":
                return await self._handle_confirm_result(card_id, raw_event)
            elif action_tag == "reject_result":
                return await self._handle_reject_result(card_id, raw_event)
            else:
                return {"status": "unknown_action", "action": action_tag}

        except Exception as e:
            logger.error(f"处理需求卡片动作失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def _handle_submit_demand(
        self,
        user_id: str,
        open_id: str,
        form_values: dict,
        raw_event: dict
    ) -> Dict:
        """处理提交需求"""
        # 提取表单数据
        demand_data = self.router.extract_demand_form_data(form_values)

        # 获取卡片token
        card_token = raw_event.get("token", "")

        # 从卡片上下文获取chat_id
        card_context = await self.demand_service.get_card_context(card_token)

        if not card_context or not card_context.get("chat_id"):
            return {"status": "error", "message": "无法获取群信息，请重试"}

        chat_id = card_context["chat_id"]

        # 获取用户名称
        created_by_name = raw_event.get("sender_name", open_id)

        # 创建需求（create_demand内部会创建话题）
        demand = await self.demand_service.create_demand(
            chat_id=chat_id,
            title=demand_data["title"],
            description=demand_data["description"],
            created_by=user_id,
            created_by_name=created_by_name,
            dimensions=demand_data.get("dimensions", []),
            time_range=demand_data.get("time_range", ""),
            priority=demand_data.get("priority", "normal")
        )

        # 发送口径确认卡片
        card = DemandCardBuilder.build_scope_confirm_card(
            title=demand.title,
            description=demand.description
        )

        response = await self.topic_service.send_card_to_topic(
            chat_id=chat_id,
            root_id=demand.root_id,
            card=card,
            sender_id="bot",
            sender_name="AI助手"
        )

        # 更新需求的卡片信息
        await self.demand_service.update_card_info(
            requirement_id=demand.requirement_id,
            card_message_id=response.message_id,
            card_token=card_token  # 保存提交卡的token
        )

        # 更新需求状态
        await self.demand_service.update_demand_status(
            requirement_id=demand.requirement_id,
            status=DemandStatus.PENDING
        )

        # 删除旧的卡片上下文
        await self.demand_service.delete_card_context(card_token)

        return {
            "status": "ok",
            "requirement_id": demand.requirement_id,
            "message": "需求已创建，请确认口径"
        }

    async def _handle_confirm_scope(self, card_id: str, raw_event: dict) -> Dict:
        """处理确认口径"""
        # 获取对应的需求
        demand = await self.demand_service.get_demand_by_card(card_id)

        if not demand:
            return {"status": "error", "message": "未找到对应的需求"}

        # 更新需求状态为分析中
        demand = await self.demand_service.update_demand_status(
            requirement_id=demand.requirement_id,
            status=DemandStatus.ANALYZING
        )

        # 发送分析中卡片
        card = DemandCardBuilder.build_analyzing_card(title=demand.title)

        await self.topic_service.update_card_in_topic(
            message_id=demand.card_message_id,
            card=card
        )

        # TODO: 调用Claude进行分析
        # 这里可以调用Claude进行分析，然后将结果发送到话题

        return {
            "status": "ok",
            "requirement_id": demand.requirement_id,
            "message": "口径已确认，开始分析"
        }

    async def _handle_confirm_result(self, card_id: str, raw_event: dict) -> Dict:
        """处理确认结果"""
        demand = await self.demand_service.get_demand_by_card(card_id)

        if not demand:
            return {"status": "error", "message": "未找到对应的需求"}

        # 完成需求
        demand = await self.demand_service.complete_demand(
            requirement_id=demand.requirement_id
        )

        return {
            "status": "ok",
            "requirement_id": demand.requirement_id,
            "message": "需求已完成"
        }

    async def _handle_reject_result(self, card_id: str, raw_event: dict) -> Dict:
        """处理驳回结果"""
        demand = await self.demand_service.get_demand_by_card(card_id)

        if not demand:
            return {"status": "error", "message": "未找到对应的需求"}

        # 更新需求状态为待处理（可以重新分析）
        demand = await self.demand_service.update_demand_status(
            requirement_id=demand.requirement_id,
            status=DemandStatus.PENDING
        )

        return {
            "status": "ok",
            "requirement_id": demand.requirement_id,
            "message": "结果已驳回，可以重新分析"
        }

    def _extract_question(self, content: str) -> str:
        """
        提取问题内容（去除@机器人部分）

        Args:
            content: 原始消息内容

        Returns:
            提取后的问题内容
        """
        # 移除@机器人标记
        import re
        # 匹配 <at user_id="xxx">xxx</at> 格式
        content = re.sub(r'<at[^>]*>[^<]*</at>', '', content)
        # 移除多余的空格
        content = ' '.join(content.split())
        return content

    def _clean_mentions(self, content: str) -> str:
        """
        清理@其他用户的内容

        去除 <at user_id="xxx">xxx</at> 格式和 @_user_* 格式

        Args:
            content: 原始消息内容

        Returns:
            清理后的内容
        """
        # 匹配 <at user_id="xxx">xxx</at> 格式
        content = re.sub(r'<at[^>]*>[^<]*</at>', '', content)
        # 匹配 @_user_* 格式
        content = re.sub(r'@_user_\S+', '', content)
        # 移除多余的空格和换行
        content = ' '.join(content.split())
        return content.strip()
