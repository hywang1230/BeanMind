"""预算相关 ORM 模型"""
from sqlalchemy import Column, String, ForeignKey, Date, Boolean, Numeric, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class Budget(BaseModel):
    """预算模型"""
    __tablename__ = "budgets"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    period_type = Column(String(20), nullable=False)  # MONTHLY, YEARLY, CUSTOM
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # 关系
    items = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_budgets_user", "user_id"),
        Index("idx_budgets_active", "is_active"),
        Index("idx_budgets_period", "start_date", "end_date"),
    )

    def __repr__(self):
        return f"<Budget(id={self.id}, name={self.name})>"


class BudgetItem(BaseModel):
    """预算项目模型"""
    __tablename__ = "budget_items"

    budget_id = Column(String(36), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    account_pattern = Column(String(100), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="CNY", nullable=False)
    spent = Column(Numeric(15, 2), default=0, nullable=False)

    # 关系
    budget = relationship("Budget", back_populates="items")

    __table_args__ = (
        Index("idx_budget_items_budget", "budget_id"),
    )

    def __repr__(self):
        return f"<BudgetItem(id={self.id}, account_pattern={self.account_pattern})>"
