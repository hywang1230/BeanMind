"""AI Agent 调用审计 ORM 模型。"""

from sqlalchemy import Column, Index, Integer, String, Text

from .base import BaseModel


class AIAgentInvocation(BaseModel):
    """AI Agent 调用审计。"""

    __tablename__ = "ai_agent_invocations"

    session_id = Column(String(36), nullable=False)
    agent_id = Column(String(50), nullable=False)
    model_profile = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="SUCCESS")
    duration_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_ai_agent_invocations_session", "session_id"),
        Index("idx_ai_agent_invocations_agent", "agent_id"),
    )
