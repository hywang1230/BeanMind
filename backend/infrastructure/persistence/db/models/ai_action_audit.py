"""AI 写操作审计 ORM 模型。"""

from sqlalchemy import Column, Index, String, Text

from .base import BaseModel


class AIActionAudit(BaseModel):
    """AI 写操作审计。"""

    __tablename__ = "ai_action_audits"

    session_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=True)
    action_type = Column(String(50), nullable=False)
    draft_payload = Column(Text, nullable=True)
    final_payload = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="DRAFTED")
    executed_at = Column(String(40), nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_ai_action_audits_session", "session_id"),
        Index("idx_ai_action_audits_status", "status"),
    )
