"""
会话模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum as SQLEnum,
    Index, ForeignKey, JSON, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Session(Base):
    """会话模型"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    root_id = Column(String(255), nullable=False, index=True)
    card_id = Column(String(255))
    claude_session_id = Column(String(255))  # Claude内部会话ID
    state = Column(SQLEnum("created", "active", "waiting_for_user", "paused", "completed", "expired", name="session_state"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    expires_at = Column(DateTime)
    session_metadata = Column(JSON, default={})

    # 群聊相关字段
    session_type = Column(String(20), default="p2p", index=True)  # 会话类型：p2p/group
    chat_id = Column(String(64), index=True)                    # 群ID（群聊场景）
    thread_id = Column(String(64), index=True)                  # 话题ID（话题场景）
    requirement_id = Column(String(64), index=True)              # 关联需求ID

    # 关系
    messages = relationship("Message", back_populates="session")
    card = relationship("Card", back_populates="session", uselist=False)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "session_key": self.session_key,
            "user_id": self.user_id,
            "root_id": self.root_id,
            "card_id": self.card_id,
            "claude_session_id": self.claude_session_id,
            "state": self.state.value if self.state else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.session_metadata,
            "session_type": self.session_type,
            "chat_id": self.chat_id,
            "thread_id": self.thread_id,
            "requirement_id": self.requirement_id,
        }


class WaitingContext:
    """等待用户回复的上下文（Redis存储）"""

    def __init__(
        self,
        pending_question: str,
        conversation_summary: str = "",
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        additional_data: Optional[dict] = None
    ):
        self.pending_question = pending_question
        self.conversation_summary = conversation_summary
        self.created_at = created_at or datetime.now()
        self.expires_at = expires_at
        self.additional_data = additional_data or {}

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return {
            "pending_question": self.pending_question,
            "conversation_summary": self.conversation_summary,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "additional_data": self.additional_data,
        }.__str__()

    @classmethod
    def from_json(cls, json_str: str) -> "WaitingContext":
        """从JSON字符串创建"""
        import json
        data = json.loads(json_str)
        return cls(
            pending_question=data.get("pending_question", ""),
            conversation_summary=data.get("conversation_summary", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            additional_data=data.get("additional_data")
        )


class DataRequirement(Base):
    """数据需求表"""
    __tablename__ = "data_requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requirement_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)                # 需求标题
    description = Column(Text, nullable=False)                              # 需求描述
    dimensions = Column(JSON)                                              # 分析维度
    time_range = Column(String(100))                                       # 时间范围
    priority = Column(String(20), default="normal", index=True)            # 优先级：low/normal/high/urgent

    # 群聊关联
    chat_id = Column(String(64), nullable=False, index=True)              # 群ID
    thread_id = Column(String(64), unique=True, nullable=False, index=True) # 话题ID
    root_id = Column(String(64), nullable=False, index=True)              # 话题根消息ID

    # 卡片关联
    card_message_id = Column(String(64))                                   # 需求卡片消息ID
    card_token = Column(String(64))                                       # 卡片token（用于更新）

    # 状态管理
    status = Column(String(20), default="pending", index=True)             # 状态：pending/scope_confirmed/analyzing/waiting_feedback/completed/cancelled

    # 用户信息
    created_by = Column(String(64), nullable=False, index=True)            # 创建人user_id
    created_by_name = Column(String(100))                                  # 创建人名称
    assigned_to = Column(String(64))                                      # 指派人user_id

    # 时间信息
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime)

    # 分析结果
    analysis_result = Column(JSON)                                        # 分析结果
    feedback = Column(Text)                                               # 用户反馈

    # 元数据（注意：metadata是SQLAlchemy保留字，使用meta_data）
    meta_data = Column(JSON, default={})

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "requirement_id": self.requirement_id,
            "title": self.title,
            "description": self.description,
            "dimensions": self.dimensions,
            "time_range": self.time_range,
            "priority": self.priority,
            "chat_id": self.chat_id,
            "thread_id": self.thread_id,
            "root_id": self.root_id,
            "card_message_id": self.card_message_id,
            "card_token": self.card_token,
            "status": self.status,
            "created_by": self.created_by,
            "created_by_name": self.created_by_name,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "analysis_result": self.analysis_result,
            "feedback": self.feedback,
            "metadata": self.meta_data,  # 返回时使用metadata键名，但内部使用meta_data
        }


class ThreadMessage(Base):
    """话题消息表"""
    __tablename__ = "thread_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(64), unique=True, nullable=False, index=True)
    thread_id = Column(String(64), nullable=False, index=True)
    parent_id = Column(String(64), index=True)                             # 父消息ID
    root_id = Column(String(64), nullable=False, index=True)               # 根消息ID

    content = Column(Text, nullable=False)
    message_type = Column(String(20))                                      # 消息类型：text/image/card
    sender_id = Column(String(64), index=True)
    sender_name = Column(String(100))

    created_at = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "parent_id": self.parent_id,
            "root_id": self.root_id,
            "content": self.content,
            "message_type": self.message_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
