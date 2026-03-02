"""
卡片模型
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Index, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from .session import Base


class Card(Base):
    """卡片模型"""
    __tablename__ = "cards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    card_id = Column(String(255), unique=True, nullable=False, index=True)
    session_key = Column(String(255), nullable=False, index=True)
    card_data = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)

    # 外键
    session_key_fk = Column(String(255), ForeignKey("sessions.session_key"))

    # 关系
    session = relationship("Session", back_populates="card")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "card_id": self.card_id,
            "session_key": self.session_key,
            "card_data": self.card_data,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
