"""AI 会话 ORM 模型。"""

from sqlalchemy import Column, Index, String, Text

from .base import BaseModel


class AISession(BaseModel):
    """AI 会话持久化模型。"""

    __tablename__ = "ai_sessions"

    session_id = Column(String(36), nullable=False, unique=True)
    title = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    last_message_preview = Column(String(255), nullable=True)
    messages_json = Column(Text, nullable=False, default="[]")

    __table_args__ = (
        Index("idx_ai_sessions_session", "session_id"),
        Index("idx_ai_sessions_status", "status"),
    )
