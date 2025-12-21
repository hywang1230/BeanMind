"""账户相关的响应 DTO

定义账户 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class AccountResponse(BaseModel):
    """
    账户信息响应
    """
    name: str = Field(..., description="账户名称")
    account_type: str = Field(..., description="账户类型")
    currencies: List[str] = Field(..., description="支持的货币列表")
    is_active: bool = Field(..., description="是否活跃")
    open_date: Optional[str] = Field(None, description="开户日期")
    close_date: Optional[str] = Field(None, description="关闭日期")
    depth: int = Field(..., description="账户层级深度")
    parent: Optional[str] = Field(None, description="父账户名称")
    meta: Dict = Field(default_factory=dict, description="元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Assets:Bank:Checking",
                "account_type": "Assets",
                "currencies": ["CNY", "USD"],
                "is_active": True,
                "open_date": "2025-01-01T00:00:00",
                "close_date": None,
                "depth": 3,
                "parent": "Assets:Bank",
                "meta": {}
            }
        }


class AccountListResponse(BaseModel):
    """
    账户列表响应
    """
    accounts: List[AccountResponse] = Field(..., description="账户列表")
    total: int = Field(..., description="总数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "accounts": [
                    {
                        "name": "Assets:Bank",
                        "account_type": "Assets",
                        "currencies": ["CNY"],
                        "is_active": True,
                        "open_date": "2025-01-01T00:00:00",
                        "close_date": None,
                        "depth": 2,
                        "parent": "Assets",
                        "meta": {}
                    }
                ],
                "total": 1
            }
        }


class AccountBalanceResponse(BaseModel):
    """
    账户余额响应
    """
    account_name: str = Field(..., description="账户名称")
    balances: Dict[str, str] = Field(..., description="余额字典（货币 -> 金额）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_name": "Assets:Bank:Checking",
                "balances": {
                    "CNY": "10000.00",
                    "USD": "100.00"
                }
            }
        }


class AccountSummaryResponse(BaseModel):
    """
    账户摘要响应
    """
    total_count: int = Field(..., description="总账户数")
    active_count: int = Field(..., description="活跃账户数")
    closed_count: int = Field(..., description="关闭账户数")
    by_type: Dict[str, Dict] = Field(..., description="按类型统计")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_count": 10,
                "active_count": 8,
                "closed_count": 2,
                "by_type": {
                    "Assets": {"count": 5, "active": 4},
                    "Expenses": {"count": 3, "active": 3}
                }
            }
        }


class SuggestAccountNameResponse(BaseModel):
    """
    建议账户名称响应
    """
    suggested_name: str = Field(..., description="建议的账户名称")
    is_valid: bool = Field(..., description="名称是否有效")
    
    class Config:
        json_schema_extra = {
            "example": {
                "suggested_name": "Expenses:Food:Dining",
                "is_valid": True
            }
        }
