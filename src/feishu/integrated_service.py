"""
集成的飞书长连接服务 - 单进程版本（修复版）
"""
import asyncio
import logging
import json
from typing import Optional, Callable, Awaitable, Dict, Any
from lark_oapi.ws import Client as WsClient
from lark_oapi import Client
from src.feishu.enhanced_client import EnhancedFeishuClient
from src.feishu.message_parser import MessageParser, MessageDeduplicator
from src.feishu.event_handler import GroupPolicyChecker
from src.config import settings
from src.utils.logger import logger


class IntegratedFeishuService:
    """集成的飞书服务 - 单进程长连接 + API"""

    def __init__(
        self,
        message_handler: Callable[[Dict[str, Any]], Awaitable[None]],
        bot_user_id: Optional[str] = None
    ):
        """
        初始化集成的飞书服务

        Args:
            message_handler: 消息处理回调函数
            bot_user_id: 机器人的用户 ID（用于 @提及检测）
        """
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self.message_handler = message_handler
        self.bot_user_id = bot_user_id

        # HTTP 客户端（用于发送消息）
        self.http_client = EnhancedFeishuClient(
            app_id=self.app_id,
            app_secret=self.app_secret
        )

        # WebSocket 客户端（用于接收消息）
        self.ws_client: Optional[WsClient] = None
        self._running = False

        # 消息去重器
        self.deduplicator = MessageDeduplicator()

        # 消息历史
        self.message_history = {}
        self.max_history = 10

        # 群组策略检查器
        self.group_policy = GroupPolicyChecker({
            "default": "open",  # 默认开放
            "groups": {}
        })

    async def start(self) -> None:
        """启动服务"""
        if self._running:
            logger.warning("服务已在运行中")
            return

        logger.info(f"启动集成飞书服务，应用 ID: {self.app_id}")

        # 创建 WebSocket 客户端（会自动连接）
        self.ws_client = WsClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=self._handle_event,
            auto_reconnect=True
        )

        self._running = True
        logger.info("集成飞书服务已启动（WebSocket 自动连接）")

    async def stop(self) -> None:
        """停止服务"""
        logger.info("正在停止集成飞书服务")
        self._running = False
        # WebSocket 客户端没有显式的停止方法
        logger.info("集成飞书服务已停止")

    async def _handle_event(self, event: Dict[str, Any]) -> None:
        """
        处理飞书事件（WebSocket 回调）

        Args:
            event: 飞书事件数据
        """
        if not self._running:
            return  # 服务已停止，忽略事件

        try:
            header = event.get("header", {})
            event_type = header.get("event_type", "")

            logger.info(f"收到飞书事件: {event_type}")

            # 根据事件类型分发
            if event_type == "im.message.receive_v1":
                await self._handle_message_event(event)
            elif event_type == "card.action.trigger":
                await self._handle_card_action_event(event)
            else:
                logger.debug(f"忽略事件类型: {event_type}")

        except Exception as e:
            logger.error(f"处理事件失败: {e}", exc_info=True)

    async def _handle_message_event(self, event: Dict[str, Any]) -> None:
        """处理消息事件"""
        event_data = event.get("event", {})
        message = event_data.get("message", {})

        # 提取消息 ID
        message_id = message.get("message_id", "")

        # 消息去重
        if self.deduplicator.is_duplicate(message_id):
            logger.debug(f"消息已处理过，跳过: {message_id}")
            return

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
        await self.message_handler({
            "type": "message",
            "parsed": parsed,
            "event": event
        })

    async def _handle_card_action_event(self, event: Dict[str, Any]) -> None:
        """处理卡片动作事件"""
        event_data = event.get("event", {})
        action = event_data.get("action", {})

        logger.info(f"收到卡片动作: {action}")

        # 调用消息处理器
        await self.message_handler({
            "type": "card_action",
            "action": action,
            "event": event
        })

    def _save_to_history(self, parsed):
        """保存消息到历史记录"""
        user_id = parsed.sender_id

        if user_id not in self.message_history:
            self.message_history[user_id] = []

        history = self.message_history[user_id]

        # 添加到历史
        history.append({
            "role": "user",
            "content": parsed.text,
            "message_type": parsed.message_type.value,
            "message_id": parsed.message_id,
            "timestamp": asyncio.get_event_loop().time()
        })

        # 限制历史长度
        if len(history) > self.max_history:
            self.message_history[user_id] = history[-self.max_history:]

    def get_history(self, user_id: str) -> list:
        """获取用户的消息历史"""
        return self.message_history.get(user_id, [])

    def clear_history(self, user_id: str):
        """清除用户的消息历史"""
        if user_id in self.message_history:
            del self.message_history[user_id]
            logger.info(f"已清除用户 {user_id} 的消息历史")

    # ============ HTTP API 方法（委托给 http_client）============

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: str = "text",
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送消息"""
        return await self.http_client.send_message(
            user_id, content, message_type, root_id
        )

    async def send_card(
        self,
        user_id: str,
        card: Dict[str, Any],
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送卡片"""
        return await self.http_client.send_card(
            user_id, card, root_id
        )

    async def update_card(
        self,
        token: str,
        card: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新卡片"""
        return await self.http_client.update_card(token, card)

    async def send_image(
        self,
        user_id: str,
        image_key: str,
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送图片"""
        return await self.http_client.send_image(
            user_id, image_key, root_id
        )

    async def send_file(
        self,
        user_id: str,
        file_key: str,
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送文件"""
        return await self.http_client.send_file(
            user_id, file_key, root_id
        )

    @property
    def is_running(self) -> bool:
        """检查服务是否在运行"""
        return self._running


# 全局服务实例
feishu_service: Optional[IntegratedFeishuService] = None


async def get_feishu_service() -> IntegratedFeishuService:
    """获取飞书服务实例"""
    global feishu_service
    return feishu_service


async def init_feishu_service(
    message_handler: Callable[[Dict[str, Any]], Awaitable[None]],
    bot_user_id: Optional[str] = None
) -> IntegratedFeishuService:
    """
    初始化飞书服务

    Args:
        message_handler: 消息处理回调函数
        bot_user_id: 机器人的用户 ID

    Returns:
        飞书服务实例
    """
    global feishu_service

    if feishu_service is None:
        feishu_service = IntegratedFeishuService(
            message_handler=message_handler,
            bot_user_id=bot_user_id
        )
        await feishu_service.start()

    return feishu_service
