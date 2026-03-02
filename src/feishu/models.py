"""
飞书数据模型
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeishuMessage:
    """飞书消息"""
    message_id: str
    user_id: str
    parent_id: Optional[str]
    root_id: Optional[str]
    content: str
    message_type: str
    card_id: Optional[str] = None


@dataclass
class FeishuCardAction:
    """飞书卡片交互"""
    card_id: str
    user_id: str
    action_tag: Optional[str]
    form_values: Optional[dict]
