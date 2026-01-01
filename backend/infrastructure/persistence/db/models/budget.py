"""预算相关 ORM 模型"""
from sqlalchemy import Column, String, ForeignKey, Date, Boolean, Numeric, Index, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


class Budget(BaseModel):
    """预算模型"""
    __tablename__ = "budgets"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False, default=0)
    period_type = Column(String(20), nullable=False)  # MONTHLY, YEARLY, CUSTOM

    # 循环预算相关字段
    cycle_type = Column(String(20), nullable=False, default="NONE")  # NONE, MONTHLY, YEARLY
    carry_over_enabled = Column(Boolean, default=False, nullable=False)  # 是否启用预算延续

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # 关系
    items = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")
    cycles = relationship("BudgetCycle", back_populates="budget", cascade="all, delete-orphan")

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


class BudgetCycle(BaseModel):
    """预算周期执行记录模型"""
    __tablename__ = "budget_cycles"

    budget_id = Column(String(36), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(Date, nullable=False)  # 周期开始日期
    period_end = Column(Date, nullable=False)  # 周期结束日期
    period_number = Column(Integer, nullable=False)  # 周期序号（从1开始）

    base_amount = Column(Numeric(15, 2), nullable=False, default=0)  # 基础预算金额
    carried_over_amount = Column(Numeric(15, 2), nullable=False, default=0)  # 上个周期延续的金额（可为负）
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)  # 总预算 = 基础金额 + 延续金额
    spent_amount = Column(Numeric(15, 2), nullable=False, default=0)  # 已花费金额

    # 关系
    budget = relationship("Budget", back_populates="cycles")

    __table_args__ = (
        Index("idx_budget_cycles_budget", "budget_id"),
        Index("idx_budget_cycles_period", "budget_id", "period_start", "period_end"),
    )

    @property
    def remaining_amount(self):
        """剩余预算"""
        return self.total_amount - self.spent_amount

    @property
    def carry_forward_amount(self):
        """可延续到下个周期的金额（剩余金额，如果启用延续）"""
        return self.remaining_amount

    def __repr__(self):
        return f"<BudgetCycle(id={self.id}, budget_id={self.budget_id}, period_start={self.period_start})>"
