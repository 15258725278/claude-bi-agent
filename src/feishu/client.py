"""
飞书客户端
"""
from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    ReplyMessageRequest, ReplyMessageRequestBody
)
from lark_oapi.api.cardkit.v1 import (
    UpdateCardRequest, UpdateCardRequestBody
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
        if root_id:
            # 发送到话题：使用 ReplyMessageRequest
            request_builder = ReplyMessageRequest.builder() \
                .message_id(root_id) \
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(json.dumps(card))
                    .msg_type("interactive")
                    .reply_in_thread(True)
                    .build()
                )

            request = request_builder.build()
            response = await self.client.im.v1.message.areply(request)
        else:
            # 发送到会话：使用 CreateMessageRequest
            request_builder = CreateMessageRequest.builder() \
                .receive_id_type("open_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("interactive")
                    .content(json.dumps(card))
                    .build()
                )

            request = request_builder.build()
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

    # ========== 群聊相关方法 ==========

    async def send_group_message(
        self,
        chat_id: str,
        content: str,
        message_type: str = "text",
        root_id: Optional[str] = None
    ) -> dict:
        """
        发送群聊消息

        Args:
            chat_id: 群ID
            content: 消息内容
            message_type: 消息类型（text/image/interactive等）
            root_id: 话题根消息ID（发送到话题时需要）

        Returns:
            消息响应数据
        """
        if root_id:
            # 发送到话题：使用 ReplyMessageRequest
            content_str = content if message_type != "text" else json.dumps({"text": content})
            request_builder = ReplyMessageRequest.builder() \
                .message_id(root_id) \
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(content_str)
                    .msg_type(message_type)
                    .reply_in_thread(True)
                    .build()
                )

            request = request_builder.build()
            response = await self.client.im.v1.message.areply(request)
        else:
            # 发送到群聊：使用 CreateMessageRequest
            request_builder = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type(message_type)
                    .content(json.dumps({"text": content}) if message_type == "text" else content)
                    .build()
                )

            request = request_builder.build()
            response = await self.client.im.v1.message.acreate(request)

        if not response.success():
            raise Exception(f"发送群聊消息失败: {response.code} {response.msg}")

        return response.data

    async def create_thread_by_reply(
        self,
        message_id: str,
        content: str,
        message_type: str = "text"
    ) -> dict:
        """
        通过回复消息创建话题

        根据飞书官方文档，使用回复消息接口并设置 reply_in_thread=True 来创建话题。
        回复的那条消息的 message_id 就是话题的 root_id 和 thread_id。

        Args:
            message_id: 要回复的消息ID（即用户@机器人的那条消息）
            content: 回复内容
            message_type: 消息类型（text/interactive等）

        Returns:
            话题信息（包含root_id, thread_id, message_id）
        """
        content_str = content if message_type != "text" else json.dumps({"text": content})

        request_builder = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content_str)
                .msg_type(message_type)
                .reply_in_thread(True)
                .build()
            )

        request = request_builder.build()
        response = await self.client.im.v1.message.areply(request)

        if not response.success():
            raise Exception(f"回复消息创建话题失败: {response.code} {response.msg}")

        # 回复的消息ID就是话题的根ID
        # 响应数据在 response.data 中
        if response.data:
            return {
                "root_id": response.data.message_id,
                "thread_id": response.data.thread_id if response.data.thread_id else response.data.message_id,
                "message_id": response.data.message_id,
            }
        else:
            # 如果没有data字段，返回空值
            return {
                "root_id": None,
                "thread_id": None,
                "message_id": None,
            }

    async def send_card_to_thread(
        self,
        chat_id: str,
        root_id: str,
        card: dict
    ) -> dict:
        """
        发送卡片到话题

        Args:
            chat_id: 群ID
            root_id: 话题根消息ID
            card: 卡片内容（JSON格式）

        Returns:
            消息响应数据
        """
        # 使用 ReplyMessageRequest 在话题中回复
        request_builder = ReplyMessageRequest.builder() \
            .message_id(root_id) \
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(json.dumps(card))
                .msg_type("interactive")
                .reply_in_thread(True)
                .build()
            )

        request = request_builder.build()

        response = await self.client.im.v1.message.areply(request)

        if not response.success():
            raise Exception(f"发送卡片到话题失败: {response.code} {response.msg}")

        return response.data

    async def update_card_by_message(
        self,
        message_id: str,
        card: dict
    ) -> dict:
        """
        通过message_id更新卡片

        Args:
            message_id: 消息ID
            card: 新的卡片内容（JSON格式）

        Returns:
            更新响应数据
        """
        request = UpdateCardRequest.builder() \
            .message_id(message_id) \
            .request_body(
                UpdateCardRequestBody.builder()
                .card(json.dumps(card))
                .build()
            ) \
            .build()

        response = await self.client.cardkit.v1.card.aupdate(request)

        if not response.success():
            raise Exception(f"更新卡片失败: {response.code} {response.msg}")

        return response.data

    async def update_card_by_token(
        self,
        card_token: str,
        card: dict
    ) -> dict:
        """
        通过card_token更新卡片

        Args:
            card_token: 卡片token
            card: 新的卡片内容（JSON格式）

        Returns:
            更新响应数据
        """
        # 使用card_token的更新方式
        # 注意：飞书API中，使用card_token更新需要通过不同的方式
        # 这里暂时使用message_id方式，后续可根据需要调整
        raise NotImplementedError("通过card_token更新卡片功能待实现")

    async def send_group_ack_emoji(self, chat_id: str, root_id: Optional[str] = None) -> dict:
        """
        发送群聊确认表情（表示正在处理）

        Args:
            chat_id: 群ID
            root_id: 话题根消息ID（可选）

        Returns:
            消息响应数据
        """
        return await self.send_group_message(
            chat_id=chat_id,
            content="👌",
            root_id=root_id
        )
