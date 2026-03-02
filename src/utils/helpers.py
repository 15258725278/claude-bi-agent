"""
工具函数
"""
import json
import re
from datetime import datetime
from typing import Any


def extract_text_from_message(message: dict) -> str:
    """从消息中提取文本"""
    content = message.get("content", "{}")
    try:
        content_dict = json.loads(content)
        text = content_dict.get("text", "")
        # 去除@mention
        text = re.sub(r'<at[^>]*>', '', text)
        text = re.sub(r'</at>', '', text)
        return text.strip()
    except:
        return ""


def parse_feishu_message(message: dict) -> dict:
    """解析飞书消息"""
    content = message.get("content", "{}")
    try:
        content_dict = json.loads(content)
    except:
        content_dict = {}

    return {
        "message_id": message.get("message_id"),
        "parent_id": message.get("parent_id"),
        "root_id": message.get("root_id"),
        "text": extract_text_from_message(message),
        "chat_id": message.get("chat_id"),
        "chat_type": message.get("chat_type"),
        "sender": message.get("sender"),
    }


def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def sanitize_user_input(text: str) -> str:
    """清理用户输入"""
    # 移除多余的空格
    text = " ".join(text.split())

    # 移除特殊字符（基本安全过滤）
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    return text


def truncate_text(text: str, max_length: int = 1000) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def safe_json_dumps(obj: Any) -> str:
    """安全的JSON序列化"""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return json.dumps({})


def get_user_id_from_key(session_key: str) -> str:
    """从会话键中获取用户ID"""
    return session_key.split(":")[0]


def get_root_id_from_key(session_key: str) -> str:
    """从会话键中获取根消息ID"""
    parts = session_key.split(":")
    if len(parts) >= 2:
        return parts[1]
    return ""
