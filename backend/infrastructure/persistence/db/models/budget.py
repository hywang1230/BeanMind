"""月度分类预算 ORM 模型。"""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import BaseModel


class MonthlyBudget(BaseModel):
    __tablename__ = "monthly_budgets"

    month = Column(String(7), nullable=False)
    items = relationship(
        "MonthlyBudgetItem",
        back_populates="budget",
        cascade="all, delete-orphan",
        order_by="MonthlyBudgetItem.display_order",
    )

    __table_args__ = (
        UniqueConstraint("month", name="uq_monthly_budget_month"),
        Index("idx_monthly_budgets_month", "month"),
    )


class MonthlyBudgetItem(BaseModel):
    __tablename__ = "monthly_budget_items"

    budget_id = Column(
        String(36),
        ForeignKey("monthly_budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    account_pattern = Column(Text, nullable=False)
    amount_text = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)

    budget = relationship("MonthlyBudget", back_populates="items")

    __table_args__ = (
        Index("idx_monthly_budget_items_budget_order", "budget_id", "display_order"),
    )
