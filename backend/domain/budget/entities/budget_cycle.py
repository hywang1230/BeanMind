"""预算周期执行记录领域实体"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import date


@dataclass
class BudgetCycle:
    """预算周期执行记录实体

    用于记录循环预算每个周期的执行情况
    """
    id: str
    budget_id: str
    period_start: date  # 周期开始日期
    period_end: date  # 周期结束日期
    period_number: int  # 周期序号（从1开始）

    base_amount: Decimal  # 基础预算金额
    carried_over_amount: Decimal  # 上个周期延续的金额（可为负）
    total_amount: Decimal  # 总预算 = 基础金额 + 延续金额
    spent_amount: Decimal  # 已花费金额

    created_at: Optional[date] = None
    updated_at: Optional[date] = None

    def __post_init__(self):
        """验证周期数据"""
        if self.period_end < self.period_start:
            raise ValueError("周期结束日期不能早于开始日期")

        if self.period_number < 1:
            raise ValueError("周期序号必须大于等于1")

        if self.base_amount < 0:
            raise ValueError("基础预算金额不能为负数")

        if self.spent_amount < 0:
            raise ValueError("已花费金额不能为负数")

        # 确保使用 Decimal
        if not isinstance(self.base_amount, Decimal):
            self.base_amount = Decimal(str(self.base_amount))
        if not isinstance(self.carried_over_amount, Decimal):
            self.carried_over_amount = Decimal(str(self.carried_over_amount))
        if not isinstance(self.total_amount, Decimal):
            self.total_amount = Decimal(str(self.total_amount))
        if not isinstance(self.spent_amount, Decimal):
            self.spent_amount = Decimal(str(self.spent_amount))

    @property
    def remaining_amount(self) -> Decimal:
        """剩余预算"""
        return self.total_amount - self.spent_amount

    @property
    def carry_forward_amount(self) -> Decimal:
        """可延续到下个周期的金额"""
        return self.remaining_amount

    @property
    def usage_rate(self) -> float:
        """使用率（百分比）"""
        if self.total_amount == 0:
            return 0.0
        return float((self.spent_amount / self.total_amount) * 100)

    def is_over_budget(self) -> bool:
        """是否超预算"""
        return self.spent_amount > self.total_amount

    def is_warning(self, threshold: float = 80.0) -> bool:
        """是否达到警告阈值"""
        return self.usage_rate >= threshold

    def update_spent(self, amount: Decimal):
        """更新已花费金额"""
        if amount < 0:
            raise ValueError("已花费金额不能为负数")
        self.spent_amount = amount
