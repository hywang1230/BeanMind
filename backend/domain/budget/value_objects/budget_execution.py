"""预算执行值对象"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class BudgetStatus(str, Enum):
    """预算状态"""
    NORMAL = "NORMAL"  # 正常
    WARNING = "WARNING"  # 警告（达到80%）
    OVER = "OVER"  # 超支


@dataclass
class BudgetExecution:
    """预算执行情况值对象
    
    用于表示预算的执行情况
    """
    budget_id: str
    budget_name: str
    total_amount: Decimal
    total_spent: Decimal
    execution_rate: float
    status: BudgetStatus
    warning_threshold: float = 80.0
    
    @property
    def remaining(self) -> Decimal:
        """剩余预算"""
        return self.total_amount - self.total_spent
    
    @classmethod
    def calculate(
        cls,
        budget_id: str,
        budget_name: str,
        total_amount: Decimal,
        total_spent: Decimal,
        warning_threshold: float = 80.0
    ) -> "BudgetExecution":
        """计算预算执行情况
        
        Args:
            budget_id: 预算ID
            budget_name: 预算名称
            total_amount: 预算总金额
            total_spent: 已花费总金额
            warning_threshold: 警告阈值（百分比）
            
        Returns:
            预算执行情况对象
        """
        # 计算执行率
        if total_amount == 0:
            execution_rate = 0.0
        else:
            execution_rate = float((total_spent / total_amount) * 100)
        
        # 判断状态
        if execution_rate >= 100:
            status = BudgetStatus.OVER
        elif execution_rate >= warning_threshold:
            status = BudgetStatus.WARNING
        else:
            status = BudgetStatus.NORMAL
        
        return cls(
            budget_id=budget_id,
            budget_name=budget_name,
            total_amount=total_amount,
            total_spent=total_spent,
            execution_rate=execution_rate,
            status=status,
            warning_threshold=warning_threshold
        )
    
    def get_status_color(self) -> str:
        """获取状态对应的颜色"""
        color_map = {
            BudgetStatus.NORMAL: "green",
            BudgetStatus.WARNING: "orange",
            BudgetStatus.OVER: "red"
        }
        return color_map.get(self.status, "gray")
