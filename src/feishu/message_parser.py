"""
消息解析器 - 从飞书消息中提取内容和元数据
"""
import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    POST = "post"
    INTERACTIVE = "interactive"


@dataclass
class ParsedMessage:
    """解析后的消息"""
    message_type: MessageType
    text: str
    content: Dict[str, Any]
    sender_id: str
    message_id: str
    root_id: Optional[str] = None
    parent_id: Optional[str] = None
    mentions: List[str] = None  # @提及的用户 ID 列表
    image_key: Optional[str] = None
    file_key: Optional[str] = None

    def __post_init__(self):
        if self.mentions is None:
            self.mentions = []


class MessageParser:
    """消息解析器"""

    # @提及的正则表达式
    MENTION_PATTERN = re.compile(r'<at user_id="([^"]+)">[^<]*</at>')

    @staticmethod
    def parse(message_data: Dict[str, Any]) -> ParsedMessage:
        """
        解析飞书消息

        Args:
            message_data: 飞书消息数据

        Returns:
            ParsedMessage 对象
        """
        # 提取基本信息
        message = message_data.get("message", {})
        sender = message.get("sender", {}).get("sender_id", {}).get("user_id", "")
        message_id = message.get("message_id", "")
        root_id = message.get("root_id") or None
        parent_id = message.get("parent_id") or None

        # 解析消息类型和内容
        content_str = message.get("content", "{}")
        if isinstance(content_str, str):
            content = json.loads(content_str)
        else:
            content = content_str

        msg_type = content.get("msg_type", "text")

        # 根据类型解析
        if msg_type == MessageType.TEXT.value:
            return MessageParser._parse_text_message(
                content, sender, message_id, root_id, parent_id
            )
        elif msg_type == MessageType.IMAGE.value:
            return MessageParser._parse_image_message(
                content, sender, message_id, root_id, parent_id
            )
        elif msg_type == MessageType.FILE.value:
            return MessageParser._parse_file_message(
                content, sender, message_id, root_id, parent_id
            )
        elif msg_type == MessageType.POST.value:
            return MessageParser._parse_post_message(
                content, sender, message_id, root_id, parent_id
            )
        else:
            # 默认文本处理
            return MessageParser._parse_text_message(
                content, sender, message_id, root_id, parent_id
            )

    @staticmethod
    def _parse_text_message(
        content: Dict[str, Any],
        sender_id: str,
        message_id: str,
        root_id: Optional[str],
        parent_id: Optional[str]
    ) -> ParsedMessage:
        """解析文本消息"""
        text = content.get("text", "")

        # 提取 @提及
        mentions = MessageParser._extract_mentions(text)

        # 清理文本（移除 @提及标签，只保留用户名）
        clean_text = MessageParser.MENTION_PATTERN.sub(r'@', text)

        return ParsedMessage(
            message_type=MessageType.TEXT,
            text=clean_text,
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            root_id=root_id,
            parent_id=parent_id,
            mentions=mentions
        )

    @staticmethod
    def _parse_image_message(
        content: Dict[str, Any],
        sender_id: str,
        message_id: str,
        root_id: Optional[str],
        parent_id: Optional[str]
    ) -> ParsedMessage:
        """解析图片消息"""
        image_key = content.get("image_key", "")

        return ParsedMessage(
            message_type=MessageType.IMAGE,
            text="[图片]",
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            root_id=root_id,
            parent_id=parent_id,
            image_key=image_key
        )

    @staticmethod
    def _parse_file_message(
        content: Dict[str, Any],
        sender_id: str,
        message_id: str,
        root_id: Optional[str],
        parent_id: Optional[str]
    ) -> ParsedMessage:
        """解析文件消息"""
        file_key = content.get("file_key", "")
        file_name = content.get("file_name", "文件")

        return ParsedMessage(
            message_type=MessageType.FILE,
            text=f"[文件: {file_name}]",
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            root_id=root_id,
            parent_id=parent_id,
            file_key=file_key
        )

    @staticmethod
    def _parse_post_message(
        content: Dict[str, Any],
        sender_id: str,
        message_id: str,
        root_id: Optional[str],
        parent_id: Optional[str]
    ) -> ParsedMessage:
        """解析富文本消息（Post）"""
        # 尝试提取文本内容
        post = content.get("post", {})
        title = post.get("zh_cn", {}).get("title", "")
        content_list = post.get("zh_cn", {}).get("content", [])

        # 组合文本
        text_parts = []
        if title:
            text_parts.append(title)

        for item in content_list:
            if item.get("tag") == "text":
                text_parts.append(item.get("text", ""))

        text = " ".join(text_parts)

        # 提取 @提及
        mentions = MessageParser._extract_mentions(text)
        clean_text = MessageParser.MENTION_PATTERN.sub(r'@', text)

        return ParsedMessage(
            message_type=MessageType.POST,
            text=clean_text,
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            root_id=root_id,
            parent_id=parent_id,
            mentions=mentions
        )

    @staticmethod
    def _extract_mentions(text: str) -> List[str]:
        """
        从文本中提取 @提及的用户 ID

        Args:
            text: 文本内容

        Returns:
            用户 ID 列表
        """
        mentions = []
        for match in MessageParser.MENTION_PATTERN.finditer(text):
            user_id = match.group(1)
            if user_id:
                mentions.append(user_id)

        return list(set(mentions))  # 去重

    @staticmethod
    def is_bot_mentioned(text: str, bot_user_id: str) -> bool:
        """
        检查是否 @机器人

        Args:
            text: 文本内容
            bot_user_id: 机器人的用户 ID

        Returns:
            是否被 @
        """
        mentions = MessageParser._extract_mentions(text)
        return bot_user_id in mentions


class MessageDeduplicator:
    """消息去重器"""

    def __init__(self, ttl_seconds: int = 300):
        """
        初始化去重器

        Args:
            ttl_seconds: 消息 ID 的存活时间（秒），默认 5 分钟
        """
        self._seen_messages = {}
        self._ttl = ttl_seconds

    def is_duplicate(self, message_id: str) -> bool:
        """
        检查消息是否已处理过

        Args:
            message_id: 消息 ID

        Returns:
            是否重复
        """
        import time
        now = time.time()

        # 检查是否已存在
        if message_id in self._seen_messages:
            # 检查是否过期
            if now - self._seen_messages[message_id] > self._ttl:
                # 过期了，删除并返回不重复
                del self._seen_messages[message_id]
                return False
            else:
                return True

        # 新消息，记录
        self._seen_messages[message_id] = now

        # 清理过期消息
        self._cleanup_expired()

        return False

    def _cleanup_expired(self):
        """清理过期的消息 ID"""
        import time
        now = time.time()

        expired_keys = [
            msg_id for msg_id, timestamp in self._seen_messages.items()
            if now - timestamp > self._ttl
        ]

        for msg_id in expired_keys:
            del self._seen_messages[msg_id]
