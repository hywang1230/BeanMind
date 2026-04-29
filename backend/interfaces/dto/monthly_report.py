"""月报 DTO"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerateMonthlyReportRequest(BaseModel):
    """生成月报请求"""

    report_month: str = Field(..., description="目标月份，格式 YYYY-MM")
    regenerate: bool = Field(default=False, description="是否强制重生成")


class MonthlyReportResponse(BaseModel):
    """月报响应"""

    id: str
    report_month: str
    status: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    summary_text: str
    report: Dict[str, Any]
    facts: Dict[str, Any]
    generated_at: Optional[str] = None


class MonthlyReportListResponse(BaseModel):
    """月报列表响应"""

    reports: List[MonthlyReportResponse]
    total: int
