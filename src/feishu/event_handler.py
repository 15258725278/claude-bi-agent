"""
飞书事件处理器 - 基于 OpenClaw 飞书集成方案
"""
import json
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from src.feishu.message_parser import MessageParser, MessageDeduplicator
from src.feishu.enhanced_client import EnhancedFeishuClient, PermissionError

logger = logging.getLogger(__name__)


class FeishuEventHandler:
    """飞书事件处理器"""

    def __init__(
        self,
        feishu_client: EnhancedFeishuClient,
        message_handler: Callable[[Dict[str, Any]], Awaitable[None]],
        bot_user_id: Optional[str] = None
    ):
        """
        初始化事件处理器

        Args:
            feishu_client: 飞书客户端
            message_handler: 消息处理回调函数
            bot_user_id: 机器人的用户 ID（用于 @提及检测）
        """
        self.feishu_client = feishu_client
        self.message_handler = message_handler
        self.bot_user_id = bot_user_id

        # 消息去重器
        self.deduplicator = MessageDeduplicator()

        # 消息历史（用于提供上下文）
        self.message_history = {}
        self.max_history = 10  # 最多保留 10 条历史

    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理飞书事件

        Args:
            event: 飞书事件数据

        Returns:
            响应数据
        """
        try:
            header = event.get("header", {})
            event_type = header.get("event_type", "")

            logger.info(f"收到飞书事件: {event_type}")

            # 根据事件类型分发
            if event_type == "im.message.receive_v1":
                return await self._handle_message_event(event)

            elif event_type == "card.action.trigger":
                return await self._handle_card_action_event(event)

            else:
                logger.warning(f"未知事件类型: {event_type}")
                return {"status": "ok"}

        except Exception as e:
            logger.error(f"处理事件失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def _handle_message_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理消息事件"""
        event_data = event.get("event", {})
        message = event_data.get("message", {})

        # 提取消息 ID
        message_id = message.get("message_id", "")

        # 消息去重
        if self.deduplicator.is_duplicate(message_id):
            logger.debug(f"消息已处理过，跳过: {message_id}")
            return {"status": "ok", "reason": "duplicate"}

        # 解析消息
        parsed = MessageParser.parse(event)

        logger.info(
            f"收到消息 - 类型: {parsed.message_type.value}, "
            f"发送者: {parsed.sender_id}, "
            f"内容: {parsed.text[:100]}..."
        )

        # 保存到历史记录
        self._save_to_history(parsed)

        # 调用消息处理器
        await self.message_handler(parsed)

        return {"status": "ok"}

    async def _handle_card_action_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """处理卡片动作事件"""
        event_data = event.get("event", {})
        action = event_data.get("action", {})

        logger.info(f"收到卡片动作: {action}")

        # TODO: 实现卡片动作处理逻辑
        # 例如：按钮点击、表单提交等

        return {"status": "ok"}

    def _save_to_history(self, parsed_message):
        """
        保存消息到历史记录

        Args:
            parsed_message: 解析后的消息
        """
        user_id = parsed_message.sender_id

        if user_id not in self.message_history:
            self.message_history[user_id] = []

        history = self.message_history[user_id]

        # 添加到历史
        history.append({
            "role": "user",
            "content": parsed_message.text,
            "message_type": parsed_message.message_type.value,
            "message_id": parsed_message.message_id,
            "timestamp": __import__('time').time()
        })

        # 限制历史长度
        if len(history) > self.max_history:
            self.message_history[user_id] = history[-self.max_history:]

    def get_history(self, user_id: str) -> list:
        """
        获取用户的消息历史

        Args:
            user_id: 用户 ID

        Returns:
            消息历史列表
        """
        return self.message_history.get(user_id, [])

    def clear_history(self, user_id: str):
        """
        清除用户的消息历史

        Args:
            user_id: 用户 ID
        """
        if user_id in self.message_history:
            del self.message_history[user_id]
            logger.info(f"已清除用户 {user_id} 的消息历史")


class GroupPolicyChecker:
    """群组策略检查器"""

    def __init__(self, policy_config: Dict[str, Any]):
        """
        初始化群组策略检查器

        Args:
            policy_config: 策略配置
                {
                    "default": "all",  # all | mention | admin | none
                    "whitelist": ["group_id1", "group_id2"],
                    "blacklist": ["group_id3"],
                    "groups": {
                        "group_id1": "mention",
                        "group_id2": "all"
                    }
                }
        """
        self.default_policy = policy_config.get("default", "none")
        self.whitelist = set(policy_config.get("whitelist", []))
        self.blacklist = set(policy_config.get("blacklist", []))
        self.group_policies = policy_config.get("groups", {})

    def should_respond(
        self,
        chat_id: str,
        is_group: bool,
        is_mentioned: bool,
        sender_is_admin: bool = False
    ) -> bool:
        """
        判断是否应该响应

        Args:
            chat_id: 聊天 ID
            is_group: 是否是群聊
            is_mentioned: 是否被 @提及
            sender_is_admin: 发送者是否是管理员

        Returns:
            是否应该响应
        """
        # 检查黑名单
        if chat_id in self.blacklist:
            logger.debug(f"群组 {chat_id} 在黑名单中，不响应")
            return False

        # 检查白名单
        if self.whitelist and chat_id not in self.whitelist:
            logger.debug(f"群组 {chat_id} 不在白名单中，不响应")
            return False

        # 获取该群组的策略
        policy = self.group_policies.get(chat_id, self.default_policy)

        # 根据策略判断
        if policy == "all":
            return True
        elif policy == "mention":
            return is_mentioned
        elif policy == "admin":
            return sender_is_admin
        elif policy == "none":
            return False
        else:
            logger.warning(f"未知的策略: {policy}")
            return False

    def get_policy(self, chat_id: str) -> str:
        """
        获取群组策略

        Args:
            chat_id: 群组 ID

        Returns:
            策略名称
        """
        return self.group_policies.get(chat_id, self.default_policy)

    def set_policy(self, chat_id: str, policy: str):
        """
        设置群组策略

        Args:
            chat_id: 群组 ID
            policy: 策略名称 (all | mention | admin | none)
        """
        self.group_policies[chat_id] = policy
        logger.info(f"群组 {chat_id} 的策略已设置为 {policy}")
