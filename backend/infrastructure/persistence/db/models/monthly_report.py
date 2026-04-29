"""月报 ORM 模型"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Index, DateTime

from .base import BaseModel


class MonthlyReport(BaseModel):
    """月报快照表"""

    __tablename__ = "monthly_reports"

    user_id = Column(String(36), nullable=False, default="default")
    report_month = Column(String(7), nullable=False, unique=True, comment="月份，格式 YYYY-MM")
    status = Column(String(20), nullable=False, default="READY", comment="READY/FAILED")
    model_provider = Column(String(50), nullable=True, comment="模型提供方")
    model_name = Column(String(100), nullable=True, comment="模型名称")
    summary_text = Column(Text, nullable=False, default="", comment="本月总结文本")
    report_json = Column(Text, nullable=False, default="{}", comment="完整月报 JSON")
    facts_json = Column(Text, nullable=False, default="{}", comment="结构化事实 JSON")
    generated_at = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_monthly_reports_month", "report_month"),
        Index("idx_monthly_reports_user_month", "user_id", "report_month"),
    )

    def __repr__(self) -> str:
        return f"<MonthlyReport(report_month={self.report_month}, status={self.status})>"
