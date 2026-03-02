"""
优化的飞书客户端 - 基于 OpenClaw 飞书集成方案
"""
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    create_message_request, create_message_request_body
)
from lark_oapi.api.cardkit.v1 import (
    UpdateCardRequest, UpdateCardRequestBody,
    update_card_request, update_card_request_body
)

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    """权限错误"""
    def __init__(self, message: str, grant_url: Optional[str] = None):
        super().__init__(message)
        self.grant_url = grant_url


class EnhancedFeishuClient:
    """增强的飞书客户端"""

    # 权限错误代码
    PERMISSION_ERROR_CODE = 99991672

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        初始化飞书客户端

        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 创建客户端
        self.client = Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

        # 权限错误通知缓存
        self._permission_error_notified = {}
        self._permission_error_cooldown = timedelta(minutes=5)

    def _extract_permission_error(self, response) -> Optional[PermissionError]:
        """
        从响应中提取权限错误

        Args:
            response: 飞书 API 响应

        Returns:
            PermissionError 或 None
        """
        if not hasattr(response, 'code') or response.code != self.PERMISSION_ERROR_CODE:
            return None

        # 从错误消息中提取授权链接
        message = getattr(response, 'msg', '')
        grant_url = None
        if message:
            import re
            url_match = re.search(r'https://[^\s,]+/app/[^\s,]+', message)
            if url_match:
                grant_url = url_match[0]

        return PermissionError(message, grant_url)

    async def _send_with_retry(
        self,
        send_func,
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的消息发送

        Args:
            send_func: 发送函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            API 响应数据

        Raises:
            Exception: 所有重试失败后抛出异常
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = await send_func(*args, **kwargs)

                # 检查权限错误
                perm_error = self._extract_permission_error(response)
                if perm_error:
                    logger.warning(f"权限错误: {perm_error}")
                    raise perm_error

                if not response.success():
                    raise Exception(f"API 错误: {response.code} {response.msg}")

                return response.data

            except PermissionError as e:
                # 权限错误不重试
                raise e

            except Exception as e:
                last_error = e
                logger.warning(
                    f"发送失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # 指数退避
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        # 所有重试都失败
        raise last_error

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: str = "text",
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息（带重试）

        Args:
            user_id: 用户 ID
            content: 消息内容
            message_type: 消息类型 (text, interactive, post)
            root_id: 回复的消息 ID

        Returns:
            消息数据

        Raises:
            PermissionError: 权限不足
            Exception: 其他错误
        """
        async def _send():
            builder = create_message_request.builder() \
                .receive_id_type("user_id") \
                .request_body(
                    create_message_request_body.builder()
                    .receive_id(user_id)
                    .msg_type(message_type)
                    .content(json.dumps({"text": content} if message_type == "text" else content))
                    .build()
                )

            if root_id:
                builder.root_id(root_id)

            request = builder.build()
            response = await self.client.im.v1.message.acreate(request)
            return response

        logger.debug(f"发送消息到 {user_id}: {content[:50]}...")
        return await self._send_with_retry(_send)

    async def send_card(
        self,
        user_id: str,
        card: Dict[str, Any],
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送卡片（带重试）

        Args:
            user_id: 用户 ID
            card: 卡片数据
            root_id: 回复的消息 ID

        Returns:
            卡片数据

        Raises:
            PermissionError: 权限不足
            Exception: 其他错误
        """
        async def _send():
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
            return response

        logger.debug(f"发送卡片到 {user_id}")
        return await self._send_with_retry(_send)

    async def update_card(
        self,
        token: str,
        card: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新卡片（带重试）

        Args:
            token: 卡片 token
            card: 卡片数据

        Returns:
            更新结果

        Raises:
            PermissionError: 权限不足
            Exception: 其他错误
        """
        async def _update():
            request = update_card_request.builder() \
                .token(token) \
                .request_body(
                    update_card_request_body.builder()
                    .card(json.dumps(card))
                    .build()
                ) \
                .build()

            response = await self.client.cardkit.v1.card.aupdate(request)
            return response

        logger.debug(f"更新卡片: {token}")
        return await self._send_with_retry(_update)

    async def send_image(
        self,
        user_id: str,
        image_key: str,
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送图片

        Args:
            user_id: 用户 ID
            image_key: 图片 key
            root_id: 回复的消息 ID

        Returns:
            消息数据
        """
        content = {
            "image_key": image_key
        }

        return await self.send_message(
            user_id,
            content,
            message_type="image",
            root_id=root_id
        )

    async def send_file(
        self,
        user_id: str,
        file_key: str,
        root_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送文件

        Args:
            user_id: 用户 ID
            file_key: 文件 key
            root_id: 回复的消息 ID

        Returns:
            消息数据
        """
        content = {
            "file_key": file_key
        }

        return await self.send_message(
            user_id,
            content,
            message_type="file",
            root_id=root_id
        )

    def should_notify_permission_error(self, key: str) -> bool:
        """
        检查是否应该通知权限错误（避免重复通知）

        Args:
            key: 错误键（用户 ID 或群组 ID）

        Returns:
            是否应该通知
        """
        now = datetime.now()
        last_notified = self._permission_error_notified.get(key)

        if last_notified is None:
            self._permission_error_notified[key] = now
            return True

        if now - last_notified > self._permission_error_cooldown:
            self._permission_error_notified[key] = now
            return True

        return False
