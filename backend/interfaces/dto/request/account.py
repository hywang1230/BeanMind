"""账户相关的请求 DTO

定义账户 API 的请求数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class CreateAccountRequest(BaseModel):
    """
    创建账户请求
    
    Example:
        {
            "name": "Assets:Bank:Checking",
            "account_type": "Assets",
            "currencies": ["CNY", "USD"],
            "open_date": "2025-01-01T00:00:00"
        }
    """
    name: str = Field(..., min_length=1, description="账户名称（如 Assets:Bank:Checking）")
    account_type: str = Field(..., description="账户类型（Assets/Liabilities/Equity/Income/Expenses）")
    currencies: Optional[List[str]] = Field(None, description="支持的货币列表")
    open_date: Optional[str] = Field(None, description="开户日期（ISO 格式）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Assets:Bank:Checking",
                "account_type": "Assets",
                "currencies": ["CNY", "USD"],
                "open_date": "2025-01-01T00:00:00"
            }
        }


class CloseAccountRequest(BaseModel):
    """
    关闭账户请求
    """
    close_date: Optional[str] = Field(None, description="关闭日期（ISO 格式）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "close_date": "2025-12-31T23:59:59"
            }
        }


class SuggestAccountNameRequest(BaseModel):
    """
    建议账户名称请求
    """
    account_type: str = Field(..., description="账户类型")
    category: str = Field(..., description="分类")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_type": "Expenses",
                "category": "food:dining"
            }
        }
