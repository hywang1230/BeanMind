"""AI 待确认动作 ORM 模型。"""

from sqlalchemy import Column, Float, Index, String, Text

from .base import BaseModel


class AIPendingAction(BaseModel):
    """AI 待确认动作。"""

    __tablename__ = "ai_pending_actions"

    session_id = Column(String(36), nullable=False, unique=True)
    action_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    draft_json = Column(Text, nullable=False)
    missing_fields_json = Column(Text, nullable=False, default="[]")
    assumptions_json = Column(Text, nullable=False, default="{}")
    confidence = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_ai_pending_actions_session", "session_id"),
        Index("idx_ai_pending_actions_status", "status"),
    )
