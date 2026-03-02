"""
飞书客户端
"""
from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody
)
from typing import Optional
import json


class FeishuClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.client = Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: str = "text"
    ) -> dict:
        """发送消息（使用 open_id 避免 user_id 权限问题）"""
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type(message_type)
                .content(json.dumps({"text": content}))
                .build()
            ) \
            .build()

        response = await self.client.im.v1.message.acreate(request)

        if not response.success():
            raise Exception(f"发送消息失败: {response.code} {response.msg}")

        return response.data

    async def send_card(
        self,
        user_id: str,
        card: dict,
        root_id: Optional[str] = None
    ) -> dict:
        """发送卡片（使用 open_id 避免 user_id 权限问题）"""
        builder = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
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
            raise Exception(f"发送卡片失败: {response.code} {response.msg}")

        return response.data

    async def update_card(
        self,
        token: str,
        card: dict
    ) -> dict:
        """更新卡片"""
        # TODO: 实现卡片更新功能，需要使用 lark_oapi.api.cardkit.v1
        raise NotImplementedError("卡片更新功能待实现")

    async def send_ack_emoji(self, user_id: str) -> dict:
        """发送确认表情（表示正在处理）"""
        return await self.send_message(user_id=user_id, content="👌")
