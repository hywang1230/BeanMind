"""预算项目领域实体"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import date


@dataclass
class BudgetItem:
    """预算项目实体
    
    表示预算中的单个支出类别
    """
    id: str
    budget_id: str
    account_pattern: str
    amount: Decimal
    currency: str = "CNY"
    spent: Decimal = Decimal("0")
    created_at: Optional[date] = None
    updated_at: Optional[date] = None
    
    def __post_init__(self):
        """验证预算项目数据"""
        # 验证账户模式
        if not self.account_pattern or not self.account_pattern.strip():
            raise ValueError("账户模式不能为空")
        
        # 验证金额
        if self.amount <= 0:
            raise ValueError("预算金额必须大于0")
        
        # 验证已花费金额
        if self.spent < 0:
            raise ValueError("已花费金额不能为负数")
        
        # 确保使用 Decimal
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if not isinstance(self.spent, Decimal):
            self.spent = Decimal(str(self.spent))
    
    def update_spent(self, amount: Decimal):
        """更新已花费金额"""
        if amount < 0:
            raise ValueError("已花费金额不能为负数")
        self.spent = amount
    
    def get_remaining(self) -> Decimal:
        """获取剩余预算"""
        return self.amount - self.spent
    
    def get_usage_rate(self) -> float:
        """获取使用率（百分比）"""
        if self.amount == 0:
            return 0.0
        return float((self.spent / self.amount) * 100)
    
    def is_over_budget(self) -> bool:
        """是否超预算"""
        return self.spent > self.amount
    
    def is_warning(self, threshold: float = 80.0) -> bool:
        """是否达到警告阈值（默认80%）"""
        return self.get_usage_rate() >= threshold
