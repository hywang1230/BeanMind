"""预算相关的请求 DTO

定义预算 API 的请求数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class PeriodTypeEnum(str, Enum):
    """预算周期类型"""
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"


class BudgetItemRequest(BaseModel):
    """
    预算项目请求
    
    用于创建或更新预算项目。
    """
    account_pattern: str = Field(..., min_length=1, description="账户模式（支持通配符，如 Expenses:Food:*）")
    amount: float = Field(0.0, description="预算金额（可选，若使用总预算则填0）")
    currency: str = Field(default="CNY", description="货币代码")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_pattern": "Expenses:Food:*",
                "amount": 3000.00,
                "currency": "CNY"
            }
        }


class CreateBudgetRequest(BaseModel):
    """
    创建预算请求
    
    Example:
        {
            "name": "2025年1月预算",
            "period_type": "MONTHLY",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "items": [
                {"account_pattern": "Expenses:Food:*", "amount": 3000, "currency": "CNY"},
                {"account_pattern": "Expenses:Transport:*", "amount": 500, "currency": "CNY"}
            ]
        }
    """
    name: str = Field(..., min_length=1, max_length=100, description="预算名称")
    amount: float = Field(..., gt=0, description="预算总额")
    period_type: PeriodTypeEnum = Field(..., description="周期类型")
    start_date: str = Field(..., description="开始日期（格式：YYYY-MM-DD）")
    end_date: Optional[str] = Field(None, description="结束日期（格式：YYYY-MM-DD）")
    items: List[BudgetItemRequest] = Field(default_factory=list, description="预算项目列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "2025年1月预算",
                "period_type": "MONTHLY",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "items": [
                    {"account_pattern": "Expenses:Food:*", "amount": 3000, "currency": "CNY"},
                    {"account_pattern": "Expenses:Transport:*", "amount": 500, "currency": "CNY"}
                ]
            }
        }


class UpdateBudgetRequest(BaseModel):
    """
    更新预算请求
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="预算名称")
    amount: Optional[float] = Field(None, gt=0, description="预算总额")
    period_type: Optional[PeriodTypeEnum] = Field(None, description="周期类型")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    is_active: Optional[bool] = Field(None, description="是否启用")
    items: Optional[List[BudgetItemRequest]] = Field(None, description="预算项目列表（完整替换）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "2025年1月预算 (修改)",
                "is_active": True
            }
        }


class AddBudgetItemRequest(BaseModel):
    """
    添加预算项目请求
    """
    account_pattern: str = Field(..., min_length=1, description="账户模式")
    amount: float = Field(..., gt=0, description="预算金额")
    currency: str = Field(default="CNY", description="货币代码")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_pattern": "Expenses:Entertainment:*",
                "amount": 500,
                "currency": "CNY"
            }
        }
