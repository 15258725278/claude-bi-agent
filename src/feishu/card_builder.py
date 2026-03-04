"""
卡片构建器
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
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


# ========== 需求管理相关卡片 ==========

class DemandCardBuilder:
    """需求管理卡片构建器"""

    @staticmethod
    def build_demand_submit_card() -> dict:
        """
        构建需求提交引导卡片（无表单，引导用户直接回复）

        Returns:
            需求提交卡片JSON
        """
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📋 提交数据分析需求"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "进入需求处理模式\n\n请**直接回复**您的数据分析需求，例如：\n\n• 分析最近30天各渠道的销售额\n• 对比今年和去年同期的用户增长\n• 分析某类商品的转化率趋势"
                    }
                }
            ]
        }

    @staticmethod
    def build_scope_confirm_card(
        title: str,
        description: str
    ) -> dict:
        """
        构建口径确认卡片

        Args:
            title: 需求标题
            description: 需求描述

        Returns:
            口径确认卡片JSON
        """
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🔍 需求口径确认"
                },
                "template": "yellow"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**需求标题：** {title}\n\n**需求描述：** {description}\n\n请在话题中@相关人员确认分析口径。"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 口径已确认，开始分析"
                            },
                            "type": "primary",
                            "name": "confirm_scope"
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✏️ 修改需求"
                            },
                            "name": "edit_demand"
                        }
                    ]
                }
            ]
        }

    @staticmethod
    def build_result_confirm_card(
        title: str,
        result_summary: str
    ) -> dict:
        """
        构建结果确认卡片

        Args:
            title: 需求标题
            result_summary: 分析结果摘要

        Returns:
            结果确认卡片JSON
        """
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 分析结果"
                },
                "template": "green"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**需求标题：** {title}\n\n**分析结果摘要：**\n{result_summary}\n\n请查看上方完整分析结果。"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 确认结果"
                            },
                            "type": "primary",
                            "name": "confirm_result"
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 驳回，需重新分析"
                            },
                            "name": "reject_result"
                        }
                    ]
                }
            ]
        }

    @staticmethod
    def build_analyzing_card(title: str) -> dict:
        """
        构建分析中卡片

        Args:
            title: 需求标题

        Returns:
            分析中卡片JSON
        """
        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "⏳ 正在分析"
                },
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**需求标题：** {title}\n\n正在分析数据，请稍候..."
                    }
                },
                {
                    "tag": "progress",
                    "value": "50",
                    "status": "running"
                }
            ]
        }

    @staticmethod
    def build_demand_status_card(
        requirement_id: str,
        title: str,
        status: str,
        status_text: str
    ) -> dict:
        """
        构建需求状态卡片

        Args:
            requirement_id: 需求ID
            title: 需求标题
            status: 状态码
            status_text: 状态文本

        Returns:
            需求状态卡片JSON
        """
        # 根据状态选择颜色
        template_map = {
            "pending": "blue",
            "scope_confirmed": "yellow",
            "analyzing": "orange",
            "waiting_feedback": "green",
            "completed": "green",
            "cancelled": "red"
        }
        template = template_map.get(status, "blue")

        return {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📋 需求状态"
                },
                "template": template
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**需求ID：**\n{requirement_id}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**状态：**\n{status_text}"
                            }
                        }
                    ]
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标题：** {title}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        }
