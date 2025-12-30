"""预算领域实体"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional
from enum import Enum


class PeriodType(str, Enum):
    """预算周期类型"""
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"


@dataclass
class Budget:
    """预算实体
    
    预算用于控制一段时期内的支出
    """
    id: str
    user_id: str
    name: str
    amount: Decimal
    period_type: PeriodType
    start_date: date
    end_date: Optional[date]
    is_active: bool = True
    items: List["BudgetItem"] = field(default_factory=list)
    created_at: Optional[date] = None
    updated_at: Optional[date] = None
    
    def __post_init__(self):
        """验证预算数据"""
        # 验证名称
        if not self.name or not self.name.strip():
            raise ValueError("预算名称不能为空")
        
        # 验证日期
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        
        # 验证周期类型
        if self.period_type == PeriodType.CUSTOM and not self.end_date:
            raise ValueError("自定义周期必须设置结束日期")
    
    def deactivate(self):
        """停用预算"""
        self.is_active = False
    
    def activate(self):
        """启用预算"""
        self.is_active = True
    
    def add_item(self, item: "BudgetItem"):
        """添加预算项目"""
        self.items.append(item)
    
    def remove_item(self, item_id: str):
        """移除预算项目"""
        self.items = [item for item in self.items if item.id != item_id]
    
    def get_total_amount(self) -> Decimal:
        """获取预算总金额"""
        return self.amount
    
    def get_total_spent(self) -> Decimal:
        """获取已花费总金额"""
        return sum((item.spent for item in self.items), Decimal("0"))
    
    def get_execution_rate(self) -> float:
        """获取执行率（百分比）"""
        total_amount = self.get_total_amount()
        if total_amount == 0:
            return 0.0
        return float((self.get_total_spent() / total_amount) * 100)
