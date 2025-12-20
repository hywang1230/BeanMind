"""周期任务相关 ORM 模型"""
from sqlalchemy import Column, String, ForeignKey, Date, Boolean, Text, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class RecurringRule(BaseModel):
    """周期规则模型"""
    __tablename__ = "recurring_rules"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    frequency = Column(String(50), nullable=False)  # DAILY, WEEKLY, MONTHLY, YEARLY, INTERVAL
    frequency_config = Column(Text, nullable=True)  # JSON 格式的频率配置
    transaction_template = Column(Text, nullable=False)  # JSON 格式的交易模板
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # 关系
    executions = relationship("RecurringExecution", back_populates="rule", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_recurring_rules_user", "user_id"),
        Index("idx_recurring_rules_active", "is_active"),
    )

    def __repr__(self):
        return f"<RecurringRule(id={self.id}, name={self.name})>"


class RecurringExecution(BaseModel):
    """周期任务执行记录模型"""
    __tablename__ = "recurring_executions"

    rule_id = Column(String(36), ForeignKey("recurring_rules.id", ondelete="CASCADE"), nullable=False)
    executed_date = Column(Date, nullable=False)
    transaction_id = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False)  # SUCCESS, FAILED, PENDING

    # 关系
    rule = relationship("RecurringRule", back_populates="executions")

    __table_args__ = (
        Index("idx_recurring_executions_rule", "rule_id"),
        Index("idx_recurring_executions_date", "executed_date"),
        Index("idx_recurring_executions_status", "status"),
    )

    def __repr__(self):
        return f"<RecurringExecution(id={self.id}, status={self.status})>"
