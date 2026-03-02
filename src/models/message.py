"""
消息模型
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Enum as SQLEnum,
    Index, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from .session import Base


class Message(Base):
    """消息模型"""
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(String(255), nullable=False, index=True)
    message_id = Column(String(255), unique=True, nullable=False)
    parent_id = Column(String(255), index=True)
    message_type = Column(String(50), nullable=False)
    direction = Column(SQLEnum("MessageDirectionEnum", name="message_direction"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)

    # 外键
    session_key_fk = Column(String(255), ForeignKey("sessions.session_key"))

    # 关系
    session = relationship("Session", back_populates="messages")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "session_key": self.session_key,
            "message_id": self.message_id,
            "parent_id": self.parent_id,
            "message_type": self.message_type,
            "direction": self.direction.value if self.direction else None,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
