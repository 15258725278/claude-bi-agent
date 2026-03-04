"""
群聊消息路由器
"""
import json
from typing import Dict, Optional, Literal
from dataclasses import dataclass
from src.utils.logger import logger


@dataclass
class GroupMessageEvent:
    """群聊消息事件"""
    event_type: str = "im.message.receive_v1"
    chat_id: str = ""
    user_id: str = ""
    open_id: str = ""
    message_id: str = ""
    root_id: Optional[str] = None
    thread_id: Optional[str] = None
    content: str = ""
    mentions_bot: bool = False
    raw_event: Optional[dict] = None


@dataclass
class GroupMessageMode:
    """群聊消息处理模式"""
    mode: Literal["qa", "demand"]  # qa: 普通问答, demand: 需求管理
    trigger_keyword: Optional[str] = None


class GroupChatRouter:
    """群聊消息路由器"""

    # 需求触发关键词
    DEMAND_TRIGGER_KEYWORD = "帮我处理需求"

    def __init__(self):
        """初始化群聊消息路由器"""

    def parse_message_event(self, event: dict) -> Optional[GroupMessageEvent]:
        """
        解析飞书消息事件

        Args:
            event: 飞书事件对象

        Returns:
            解析后的群聊消息事件，如果不是群聊消息则返回None
        """
        try:
            event_type = event.get("header", {}).get("event_type", "")

            if event_type != "im.message.receive_v1":
                return None

            event_data = event.get("event", {})
            message = event_data.get("message", {})

            # 检查是否是群聊消息（有chat_id）
            chat_id = message.get("chat_id")
            if not chat_id:
                return None

            # 获取发送者信息
            sender = message.get("sender", {})
            sender_id = sender.get("sender_id", {})
            user_id = sender_id.get("user_id", "")
            open_id = sender_id.get("open_id", "")

            # 解析消息内容
            message_id = message.get("message_id", "")
            root_id = message.get("root_id")
            thread_id = message.get("thread_id")
            content_str = message.get("content", "{}")

            # 解析content
            content = ""
            try:
                if isinstance(content_str, str):
                    content_data = json.loads(content_str)
                    content = content_data.get("text", content_str)
                else:
                    content = str(content_str)
            except json.JSONDecodeError:
                content = content_str

            # 检查是否@了机器人
            mentions_bot = self._check_mentions_bot(message)

            return GroupMessageEvent(
                event_type=event_type,
                chat_id=chat_id,
                user_id=user_id,
                open_id=open_id,
                message_id=message_id,
                root_id=root_id,
                thread_id=thread_id,
                content=content,
                mentions_bot=mentions_bot,
                raw_event=event
            )

        except Exception as e:
            logger.error(f"解析群聊消息事件失败: {e}", exc_info=True)
            return None

    def route_message(self, event: GroupMessageEvent) -> GroupMessageMode:
        """
        路由消息到对应处理模式

        Args:
            event: 群聊消息事件

        Returns:
            消息处理模式
        """
        # 如果没有@机器人，忽略消息
        if not event.mentions_bot:
            return GroupMessageMode(mode="qa", trigger_keyword=None)

        # 检查是否包含需求触发关键词
        if self.DEMAND_TRIGGER_KEYWORD in event.content:
            logger.info(f"检测到需求管理触发关键词: {self.DEMAND_TRIGGER_KEYWORD}")
            return GroupMessageMode(mode="demand", trigger_keyword=self.DEMAND_TRIGGER_KEYWORD)

        # 默认为普通问答模式
        return GroupMessageMode(mode="qa", trigger_keyword=None)

    def _check_mentions_bot(self, message: dict) -> bool:
        """
        检查消息是否@了机器人

        Args:
            message: 消息对象

        Returns:
            是否@了机器人
        """
        try:
            content = message.get("content", "")

            # 如果content是字符串，先检查是否已经是纯文本
            if isinstance(content, str):
                # 直接检查纯文本中是否包含@标记
                # 飞书文本中的@bot格式为 <at user_id="xxx">xxx</at>
                if "<at" in content and "</at>" in content:
                    return True
                # 也检查 @_user_xxx 格式（某些情况下的简化格式）
                if "@_user" in content:
                    return True

                # 尝试解析为JSON（检查mentions字段）
                try:
                    content_data = json.loads(content)
                except json.JSONDecodeError:
                    # 不是JSON，已经在上面检查过了
                    return False

                mentions = content_data.get("mentions", [])
                for mention in mentions:
                    if mention.get("type") == "bot":
                        return True

                text = content_data.get("text", "")
                if "<at" in text and "</at>" in text:
                    return True

            # 如果content已经是dict
            elif isinstance(content, dict):
                mentions = content.get("mentions", [])
                for mention in mentions:
                    if mention.get("type") == "bot":
                        return True

                text = content.get("text", "")
                if "<at" in text and "</at>" in text:
                    return True

            return False

        except Exception as e:
            logger.warning(f"检查@bot失败: {e}")
            return False

    def extract_demand_form_data(self, form_values: dict) -> Dict:
        """
        从表单数据中提取需求信息（简化版）

        Args:
            form_values: 表单数据

        Returns:
            需求信息字典
        """
        content = form_values.get("demand_content", "")

        # 使用内容的前50个字符作为标题，完整内容作为描述
        title = content[:50] + "..." if len(content) > 50 else content

        return {
            "title": title,
            "description": content,
            "dimensions": [],
            "time_range": "",
            "priority": "normal",
        }

    def is_in_thread(self, event: GroupMessageEvent) -> bool:
        """
        检查消息是否在话题中

        Args:
            event: 群聊消息事件

        Returns:
            是否在话题中
        """
        return event.root_id is not None

    def get_session_key(self, event: GroupMessageEvent, mode: str) -> str:
        """
        根据消息和模式生成会话键

        Args:
            event: 群聊消息事件
            mode: 处理模式（qa/demand）

        Returns:
            会话键
        """
        if mode == "demand":
            # 需求模式：使用话题ID作为会话键的一部分
            thread_id = event.thread_id or event.root_id
            return f"{event.chat_id}:demand:{thread_id}"
        else:
            # 普通问答模式：每次都是新会话
            return f"{event.user_id}:qa:{event.chat_id}:{event.message_id}"
