"""AI 用户偏好 ORM 模型。"""

from sqlalchemy import Column, Float, Index, Integer, String, Text

from .base import BaseModel


class AIUserPreference(BaseModel):
    """AI 长期记忆中的低风险用户偏好。"""

    __tablename__ = "ai_user_preferences"

    user_id = Column(String(36), nullable=False, default="default")
    preference_type = Column(String(50), nullable=False)
    preference_key = Column(String(255), nullable=False)
    value_json = Column(Text, nullable=False, default="{}")
    weight = Column(Float, nullable=False, default=1.0)
    use_count = Column(Integer, nullable=False, default=1)
    last_used_at = Column(String(40), nullable=True)

    __table_args__ = (
        Index("idx_ai_user_preferences_user", "user_id"),
        Index("idx_ai_user_preferences_type", "preference_type"),
        Index("idx_ai_user_preferences_key", "preference_key"),
    )
