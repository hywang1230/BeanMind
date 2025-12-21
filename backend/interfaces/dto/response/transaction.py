"""交易相关的响应 DTO

定义交易 API 的响应数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class PostingResponse(BaseModel):
    """
    记账分录响应
    """
    account: str = Field(..., description="账户名称")
    amount: str = Field(..., description="金额")
    currency: str = Field(..., description="货币代码")
    cost: Optional[str] = Field(None, description="成本")
    cost_currency: Optional[str] = Field(None, description="成本货币")
    price: Optional[str] = Field(None, description="价格")
    price_currency: Optional[str] = Field(None, description="价格货币")
    flag: Optional[str] = Field(None, description="标记")
    meta: Dict = Field(default_factory=dict, description="元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "account": "Expenses:Food",
                "amount": "50.00",
                "currency": "CNY",
                "cost": None,
                "cost_currency": None,
                "price": None,
                "price_currency": None,
                "flag": None,
                "meta": {}
            }
        }


class TransactionResponse(BaseModel):
    """
    交易信息响应
    """
    id: str = Field(..., description="交易 ID")
    date: str = Field(..., description="交易日期")
    description: str = Field(..., description="交易描述")
    payee: Optional[str] = Field(None, description="收付款方")
    flag: Optional[str] = Field(None, description="标记")
    postings: List[PostingResponse] = Field(..., description="记账分录列表")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    links: List[str] = Field(default_factory=list, description="链接列表")
    meta: Dict = Field(default_factory=dict, description="元数据")
    transaction_type: str = Field(..., description="交易类型")
    accounts: List[str] = Field(..., description="涉及的账户列表")
    currencies: List[str] = Field(..., description="涉及的货币列表")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "txn-001",
                "date": "2025-01-15",
                "description": "午餐",
                "payee": "餐厅",
                "flag": "*",
                "postings": [
                    {
                        "account": "Expenses:Food",
                        "amount": "50.00",
                        "currency": "CNY",
                        "cost": None,
                        "cost_currency": None,
                        "price": None,
                        "price_currency": None,
                        "flag": None,
                        "meta": {}
                    },
                    {
                        "account": "Assets:Cash",
                        "amount": "-50.00",
                        "currency": "CNY",
                        "cost": None,
                        "cost_currency": None,
                        "price": None,
                        "price_currency": None,
                        "flag": None,
                        "meta": {}
                    }
                ],
                "tags": ["food", "lunch"],
                "links": [],
                "meta": {},
                "transaction_type": "expense",
                "accounts": ["Expenses:Food", "Assets:Cash"],
                "currencies": ["CNY"],
                "created_at": "2025-01-15T12:00:00",
                "updated_at": "2025-01-15T12:00:00"
            }
        }


class TransactionListResponse(BaseModel):
    """
    交易列表响应
    """
    transactions: List[TransactionResponse] = Field(..., description="交易列表")
    total: int = Field(..., description="总数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "transactions": [
                    {
                        "id": "txn-001",
                        "date": "2025-01-15",
                        "description": "午餐",
                        "payee": "餐厅",
                        "flag": "*",
                        "postings": [
                            {"account": "Expenses:Food", "amount": "50.00", "currency": "CNY", "cost": None, "cost_currency": None, "price": None, "price_currency": None, "flag": None, "meta": {}},
                            {"account": "Assets:Cash", "amount": "-50.00", "currency": "CNY", "cost": None, "cost_currency": None, "price": None, "price_currency": None, "flag": None, "meta": {}}
                        ],
                        "tags": ["food"],
                        "links": [],
                        "meta": {},
                        "transaction_type": "expense",
                        "accounts": ["Expenses:Food", "Assets:Cash"],
                        "currencies": ["CNY"],
                        "created_at": "2025-01-15T12:00:00",
                        "updated_at": "2025-01-15T12:00:00"
                    }
                ],
                "total": 1
            }
        }


class TransactionStatisticsResponse(BaseModel):
    """
    交易统计响应
    """
    total_count: int = Field(..., description="总交易数")
    by_type: Dict[str, int] = Field(..., description="按类型统计")
    by_currency: Dict[str, Dict[str, float]] = Field(..., description="按货币统计")
    income_total: Dict[str, float] = Field(..., description="总收入（按货币）")
    expense_total: Dict[str, float] = Field(..., description="总支出（按货币）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_count": 100,
                "by_type": {
                    "expense": 60,
                    "income": 30,
                    "transfer": 10
                },
                "by_currency": {
                    "CNY": {
                        "income": 10000.0,
                        "expense": 8000.0
                    },
                    "USD": {
                        "income": 500.0,
                        "expense": 300.0
                    }
                },
                "income_total": {
                    "CNY": 10000.0,
                    "USD": 500.0
                },
                "expense_total": {
                    "CNY": 8000.0,
                    "USD": 300.0
                }
            }
        }


class ValidationResultResponse(BaseModel):
    """
    验证结果响应
    """
    valid: bool = Field(..., description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "valid": False,
                "errors": ["交易不平衡，CNY: 10.00"]
            }
        }


class CategoryResponse(BaseModel):
    """
    分类响应
    """
    category: str = Field(..., description="分类名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "Food"
            }
        }
