"""
统计数据 DTO
"""
from pydantic import BaseModel, Field


class AssetOverviewResponse(BaseModel):
    """资产概览响应"""
    net_assets: float = Field(..., description="净资产")
    total_assets: float = Field(..., description="总资产")
    total_liabilities: float = Field(..., description="总负债")
    currency: str = Field(default="CNY", description="币种")


class CategoryStatisticsResponse(BaseModel):
    """类别统计响应"""
    category: str = Field(..., description="类别名称")
    amount: float = Field(..., description="金额")
    percentage: float = Field(..., description="占比（百分比）")
    count: int = Field(..., description="交易笔数")


class MonthlyTrendResponse(BaseModel):
    """月度趋势响应"""
    month: str = Field(..., description="月份 YYYY-MM")
    income: float = Field(..., description="收入")
    expense: float = Field(..., description="支出")
    net: float = Field(..., description="净收入")


class FrequentItemResponse(BaseModel):
    """常用账户/分类响应"""
    name: str = Field(..., description="账户/分类名称")
    count: int = Field(..., description="使用次数")
    last_used: str = Field(..., description="最后使用日期 YYYY-MM-DD")
