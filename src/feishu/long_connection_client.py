"""
飞书长连接客户端
"""
import json
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    create_message_request, create_message_request_body
)
from lark_oapi.ws import Client as WsClient

logger = logging.getLogger(__name__)


class FeishuLongConnectionClient:
    """飞书长连接（WebSocket）客户端"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        event_handler: Optional[Callable] = None
    ):
        """
        初始化长连接客户端

        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            event_handler: 事件处理回调函数
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.event_handler = event_handler

        # 基础客户端（用于发送消息）
        self.client = Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

        # 长连接相关
        self.ws_client: Optional[WsClient] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """建立长连接"""
        if self._running:
            logger.warning("长连接已在运行中")
            return

        logger.info(f"开始建立飞书长连接，应用ID: {self.app_id}")

        # 创建 WebSocket 客户端
        self.ws_client = WsClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=None  # TODO: 实现事件处理器
        )

        # 启动长连接任务
        self._task = asyncio.create_task(self._run())
        self._running = True

        logger.info("飞书长连接已启动")

    async def _run(self) -> None:
        """运行长连接"""
        try:
            await self.ws_client.start()
        except Exception as e:
            logger.error(f"长连接错误: {e}", exc_info=True)
            if self._running:
                # 连接断开，自动重连
                await asyncio.sleep(5)
                self._task = asyncio.create_task(self._run())

    async def disconnect(self) -> None:
        """断开长连接"""
        logger.info("正在断开飞书长连接")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Note: ws.Client doesn't have a stop method, let it run until cancelled

        logger.info("飞书长连接已断开")

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: str = "text"
    ) -> dict:
        """发送消息"""
        request = create_message_request.builder() \
            .receive_id_type("user_id") \
            .request_body(
                create_message_request_body.builder()
                .receive_id(user_id)
                .msg_type(message_type)
                .content(json.dumps({"text": content}))
                .build()
            ) \
            .build()

        response = await self.client.im.v1.message.acreate(request)

        if not response.success():
            logger.error(f"发送消息失败: {response.code} {response.msg}")
            raise Exception(f"发送消息失败: {response.code} {response.msg}")

        return response.data

    async def send_card(
        self,
        user_id: str,
        card: dict,
        root_id: Optional[str] = None
    ) -> dict:
        """发送卡片"""
        builder = create_message_request.builder() \
            .receive_id_type("user_id") \
            .request_body(
                create_message_request_body.builder()
                .receive_id(user_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .build()
            )

        if root_id:
            builder.root_id(root_id)

        request = builder.build()

        response = await self.client.im.v1.message.acreate(request)

        if not response.success():
            logger.error(f"发送卡片失败: {response.code} {response.msg}")
            raise Exception(f"发送卡片失败: {response.code} {response.msg}")

        return response.data

    async def update_card(
        self,
        token: str,
        card: dict
    ) -> dict:
        """更新卡片"""
        # TODO: 实现卡片更新功能
        raise NotImplementedError("卡片更新功能待实现")

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._running and self.ws_client is not None
