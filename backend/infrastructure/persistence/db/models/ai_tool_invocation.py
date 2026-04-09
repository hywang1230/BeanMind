"""AI 工具调用审计 ORM 模型。"""

from sqlalchemy import Column, Index, Integer, String, Text

from .base import BaseModel


class AIToolInvocation(BaseModel):
    """AI 工具调用审计。"""

    __tablename__ = "ai_tool_invocations"

    session_id = Column(String(36), nullable=False)
    skill_id = Column(String(50), nullable=False)
    tool_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="SUCCESS")
    duration_ms = Column(Integer, nullable=True)
    payload_preview = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_ai_tool_invocations_session", "session_id"),
        Index("idx_ai_tool_invocations_tool", "tool_name"),
        Index("idx_ai_tool_invocations_status", "status"),
    )
