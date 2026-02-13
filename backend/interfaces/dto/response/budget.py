"""预算相关的响应 DTO

定义预算 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class BudgetStatusEnum(str, Enum):
    """预算状态"""
    NORMAL = "normal"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class BudgetItemResponse(BaseModel):
    """
    预算项目响应
    """
    id: str = Field(..., description="项目ID")
    budget_id: str = Field(..., description="所属预算ID")
    account_pattern: str = Field(..., description="账户模式")
    amount: float = Field(..., description="预算金额")
    currency: str = Field(..., description="货币代码")
    spent: float = Field(default=0, description="已花费金额")
    remaining: float = Field(..., description="剩余金额")
    usage_rate: float = Field(..., description="使用率（百分比）")
    status: BudgetStatusEnum = Field(..., description="状态")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "item-123",
                "budget_id": "budget-456",
                "account_pattern": "Expenses:Food:*",
                "amount": 3000.00,
                "currency": "CNY",
                "spent": 1500.00,
                "remaining": 1500.00,
                "usage_rate": 50.0,
                "status": "normal"
            }
        }


class BudgetResponse(BaseModel):
    """
    预算响应
    """
    id: str = Field(..., description="预算ID")
    name: str = Field(..., description="预算名称")
    amount: float = Field(..., description="单周期预算金额")
    period_type: str = Field(..., description="周期类型")
    start_date: str = Field(..., description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    is_active: bool = Field(..., description="是否启用")
    items: List[BudgetItemResponse] = Field(default_factory=list, description="预算项目列表")
    total_budget: float = Field(..., description="预算总额")
    total_spent: float = Field(..., description="已花费总额")
    total_remaining: float = Field(..., description="剩余总额")
    overall_usage_rate: float = Field(..., description="整体使用率")
    status: BudgetStatusEnum = Field(..., description="整体状态")
    monthly_budget: float = Field(default=0, description="本月预算")
    monthly_spent: float = Field(default=0, description="本月已花费")
    monthly_remaining: float = Field(default=0, description="本月剩余")
    monthly_usage_rate: float = Field(default=0, description="本月使用率")
    monthly_status: BudgetStatusEnum = Field(default=BudgetStatusEnum.NORMAL, description="本月状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    # 循环预算相关字段
    cycle_type: str = Field(default="NONE", description="循环类型")
    carry_over_enabled: bool = Field(default=False, description="是否启用预算延续")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "budget-456",
                "name": "2025年月度预算",
                "amount": 5000.00,
                "period_type": "MONTHLY",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "is_active": True,
                "items": [],
                "total_budget": 5000.00,
                "total_spent": 2500.00,
                "total_remaining": 2500.00,
                "overall_usage_rate": 50.0,
                "status": "normal",
                "monthly_budget": 5000.00,
                "monthly_spent": 2500.00,
                "monthly_remaining": 2500.00,
                "monthly_usage_rate": 50.0,
                "monthly_status": "normal",
                "cycle_type": "MONTHLY",
                "carry_over_enabled": True,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-15T12:00:00"
            }
        }


class BudgetCycleResponse(BaseModel):
    """预算周期响应"""
    id: str = Field(..., description="周期ID")
    budget_id: str = Field(..., description="预算ID")
    period_number: int = Field(..., description="周期序号")
    period_start: str = Field(..., description="周期开始日期")
    period_end: str = Field(..., description="周期结束日期")
    base_amount: float = Field(..., description="基础预算金额")
    carried_over_amount: float = Field(..., description="延续的金额")
    total_amount: float = Field(..., description="总预算金额")
    spent_amount: float = Field(..., description="已花费金额")
    remaining_amount: float = Field(..., description="剩余金额")
    usage_rate: float = Field(..., description="使用率")
    status: BudgetStatusEnum = Field(..., description="状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cycle_1",
                "budget_id": "budget-456",
                "period_number": 1,
                "period_start": "2025-01-01",
                "period_end": "2025-01-31",
                "base_amount": 5000.0,
                "carried_over_amount": 0.0,
                "total_amount": 5000.0,
                "spent_amount": 3500.0,
                "remaining_amount": 1500.0,
                "usage_rate": 70.0,
                "status": "normal"
            }
        }


class BudgetCycleListResponse(BaseModel):
    """预算周期列表响应"""
    cycles: List[BudgetCycleResponse] = Field(..., description="周期列表")
    total: int = Field(..., description="总数")


class BudgetListResponse(BaseModel):
    """
    预算列表响应
    """
    budgets: List[BudgetResponse] = Field(..., description="预算列表")
    total: int = Field(..., description="总数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "budgets": [],
                "total": 0
            }
        }


class BudgetSummaryResponse(BaseModel):
    """
    预算概览响应
    """
    total_budgets: int = Field(..., description="预算总数")
    active_budgets: int = Field(..., description="活跃预算数")
    total_budgeted: float = Field(..., description="预算总额")
    total_spent: float = Field(..., description="已花费总额")
    overall_rate: float = Field(..., description="整体执行率")
    status_count: dict = Field(..., description="各状态数量")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_budgets": 3,
                "active_budgets": 2,
                "total_budgeted": 15000.00,
                "total_spent": 8000.00,
                "overall_rate": 53.33,
                "status_count": {
                    "normal": 1,
                    "warning": 1,
                    "exceeded": 0
                }
            }
        }
