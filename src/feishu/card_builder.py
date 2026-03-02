"""
卡片构建器
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class CardBuilder:
    """卡片构建器"""

    title: Optional[str] = None
    content: str = ""
    status: str = "处理中"
    show_progress: bool = False
    progress: int = 0
    fields: List[dict] = field(default_factory=list)
    buttons: List[dict] = field(default_factory=list)

    def build(self) -> dict:
        """构建卡片数据"""
        elements = []

        # 标题
        if self.title:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{self.title}**"
                }
            })

        # 分隔线
        elements.append({"tag": "hr"})

        # 内容
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": self.content
            }
        })

        # 进度条
        if self.show_progress:
            elements.append({
                "tag": "progress",
                "value": str(self.progress),
                "status": "running"
            })

        # 状态字段
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {
                        "tag": "plain_text",
                        "content": f"状态: {self.status}"
                    }
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "plain_text",
                        "content": f"时间: {datetime.now().strftime('%H:%M')}"
                    }
                }
            ]
        })

        # 自定义字段
        if self.fields:
            elements.append({
                "tag": "div",
                "fields": self.fields
            })

        # 按钮
        if self.buttons:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": self.buttons
            })

        return {
            "config": {
                "wide_screen_mode": True
            },
            "elements": elements
        }

    def add_button(
        self,
        text: str,
        action_type: str = "primary",
        action_tag: str = None,
        value: dict = None
    ) -> "CardBuilder":
        """添加按钮"""
        self.buttons.append({
            "tag": "button",
            "text": {
                "tag": "plain_text",
                "content": text
            },
            "type": action_type,
            "action_tag": action_tag or text,
            "value": value or {}
        })
        return self

    def add_field(
        self,
        label: str,
        value: str,
        is_short: bool = True
    ) -> "CardBuilder":
        """添加字段"""
        self.fields.append({
            "is_short": is_short,
            "text": {
                "tag": "plain_text",
                "content": f"{label}: {value}"
            }
        })
        return self
