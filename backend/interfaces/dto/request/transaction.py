"""交易相关的请求 DTO

定义交易 API 的请求数据结构。
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from decimal import Decimal


class PostingRequest(BaseModel):
    """
    记账分录请求
    
    Example:
        {
            "account": "Expenses:Food",
            "amount": "50.00",
            "currency": "CNY"
        }
    """
    account: str = Field(..., min_length=1, description="账户名称")
    amount: str = Field(..., description="金额（字符串格式）")
    currency: str = Field(..., min_length=3, max_length=3, description="货币代码（3位）")
    cost: Optional[str] = Field(None, description="成本")
    cost_currency: Optional[str] = Field(None, description="成本货币")
    price: Optional[str] = Field(None, description="价格")
    price_currency: Optional[str] = Field(None, description="价格货币")
    flag: Optional[str] = Field(None, description="标记")
    meta: Optional[Dict] = Field(None, description="元数据")
    
    @field_validator('amount', 'cost', 'price')
    @classmethod
    def validate_decimal(cls, v):
        """验证是否为有效的 Decimal 字符串"""
        if v is not None:
            try:
                Decimal(v)
            except:
                raise ValueError(f"无效的金额格式: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "account": "Expenses:Food",
                "amount": "50.00",
                "currency": "CNY"
            }
        }


class CreateTransactionRequest(BaseModel):
    """
    创建交易请求
    
    Example:
        {
            "date": "2025-01-15",
            "description": "午餐",
            "postings": [
                {"account": "Expenses:Food", "amount": "50.00", "currency": "CNY"},
                {"account": "Assets:Cash", "amount": "-50.00", "currency": "CNY"}
            ],
            "payee": "餐厅",
            "tags": ["food", "lunch"],
            "links": []
        }
    """
    date: str = Field(..., description="交易日期（YYYY-MM-DD 格式）")
    description: Optional[str] = Field(None, description="交易描述")
    postings: List[PostingRequest] = Field(..., min_length=2, description="记账分录列表（至少2个）")
    payee: Optional[str] = Field(None, description="收付款方")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    links: Optional[List[str]] = Field(None, description="链接列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-01-15",
                "description": "午餐",
                "postings": [
                    {"account": "Expenses:Food", "amount": "50.00", "currency": "CNY"},
                    {"account": "Assets:Cash", "amount": "-50.00", "currency": "CNY"}
                ],
                "payee": "餐厅",
                "tags": ["food", "lunch"],
                "links": []
            }
        }


class UpdateTransactionRequest(BaseModel):
    """
    更新交易请求
    
    所有字段都是可选的，只更新提供的字段。
    """
    date: Optional[str] = Field(None, description="交易日期")
    description: Optional[str] = Field(None, description="交易描述")
    postings: Optional[List[PostingRequest]] = Field(None, min_length=2, description="记账分录列表")
    payee: Optional[str] = Field(None, description="收付款方")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    links: Optional[List[str]] = Field(None, description="链接列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "更新后的描述",
                "payee": "新的收款方"
            }
        }


class TransactionQueryRequest(BaseModel):
    """
    交易查询请求
    
    支持多种筛选条件。
    """
    start_date: Optional[str] = Field(None, description="开始日期（YYYY-MM-DD）")
    end_date: Optional[str] = Field(None, description="结束日期（YYYY-MM-DD）")
    account: Optional[str] = Field(None, description="账户过滤")
    transaction_type: Optional[str] = Field(None, description="交易类型（expense/income/transfer/opening/other）")
    tags: Optional[List[str]] = Field(None, description="标签过滤")
    description: Optional[str] = Field(None, description="描述关键词搜索")
    limit: Optional[int] = Field(None, ge=1, le=1000, description="限制返回数量（1-1000）")
    offset: Optional[int] = Field(None, ge=0, description="偏移量")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "transaction_type": "expense",
                "limit": 20,
                "offset": 0
            }
        }


class StatisticsQueryRequest(BaseModel):
    """
    统计查询请求
    """
    start_date: str = Field(..., description="开始日期（YYYY-MM-DD）")
    end_date: str = Field(..., description="结束日期（YYYY-MM-DD）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31"
            }
        }
