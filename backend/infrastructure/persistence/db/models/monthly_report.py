"""OpenAI-compatible 月度复盘状态。"""

from sqlalchemy import Column, DateTime, Index, String, Text

from .base import BaseModel


class MonthlyReview(BaseModel):
    __tablename__ = "monthly_reviews"

    report_month = Column(String(7), nullable=False, unique=True)
    generation_status = Column(String(20), nullable=False, default="DISABLED")
    model_name = Column(String(100), nullable=True)
    facts_json = Column(Text, nullable=False, default="{}")
    pending_facts_json = Column(Text, nullable=False, default="{}")
    summary_text = Column(Text, nullable=False, default="")
    suggestions_json = Column(Text, nullable=False, default="[]")
    last_error = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_monthly_reviews_month", "report_month"),)
