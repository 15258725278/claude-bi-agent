"""
会话模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Enum as SQLEnum,
    Index, ForeignKey, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Session(Base):
    """会话模型"""
    __tablename__ = "sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    root_id = Column(String(255), nullable=False, index=True)
    card_id = Column(String(255))
    claude_session_id = Column(String(255))  # Claude内部会话ID
    state = Column(SQLEnum("SessionStateEnum", name="session_state"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    expires_at = Column(DateTime)
    session_metadata = Column(JSON, default={})

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
