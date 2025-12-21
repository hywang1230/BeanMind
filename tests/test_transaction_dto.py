"""交易 DTO 单元测试

测试交易相关的 DTO 数据结构。
"""
import pytest
from pydantic import ValidationError

from backend.interfaces.dto.request.transaction import (
    PostingRequest,
    CreateTransactionRequest,
    UpdateTransactionRequest,
    TransactionQueryRequest,
    StatisticsQueryRequest
)
from backend.interfaces.dto.response.transaction import (
    PostingResponse,
    TransactionResponse,
    TransactionListResponse,
    TransactionStatisticsResponse,
    ValidationResultResponse,
    CategoryResponse
)


class TestTransactionRequestDTO:
    """测试交易请求 DTO"""
    
    def test_posting_request_valid(self):
        """测试创建有效的 PostingRequest"""
        posting = PostingRequest(
            account="Expenses:Food",
            amount="50.00",
            currency="CNY"
        )
        
        assert posting.account == "Expenses:Food"
        assert posting.amount == "50.00"
        assert posting.currency == "CNY"
    
    def test_posting_request_invalid_amount(self):
        """测试无效的金额"""
        with pytest.raises(ValidationError):
            PostingRequest(
                account="Expenses:Food",
                amount="invalid",
                currency="CNY"
            )
    
    def test_create_transaction_request_valid(self):
        """测试创建有效的 CreateTransactionRequest"""
        request = CreateTransactionRequest(
            date="2025-01-15",
            description="午餐",
            postings=[
                PostingRequest(account="Expenses:Food", amount="50.00", currency="CNY"),
                PostingRequest(account="Assets:Cash", amount="-50.00", currency="CNY")
            ],
            payee="餐厅",
            tags=["food", "lunch"]
        )
        
        assert request.date == "2025-01-15"
        assert request.description == "午餐"
        assert len(request.postings) == 2
        assert request.payee == "餐厅"
        assert "food" in request.tags
    
    def test_create_transaction_request_insufficient_postings(self):
        """测试不足的记账分录"""
        with pytest.raises(ValidationError):
            CreateTransactionRequest(
                date="2025-01-15",
                description="测试",
                postings=[
                    PostingRequest(account="Expenses:Food", amount="50.00", currency="CNY")
                ]  # 只有一个 posting
            )
    
    def test_update_transaction_request(self):
        """测试 UpdateTransactionRequest"""
        request = UpdateTransactionRequest(
            description="更新的描述",
            payee="新的收款方"
        )
        
        assert request.description == "更新的描述"
        assert request.payee == "新的收款方"
        assert request.date is None  # 未提供的字段应为 None
    
    def test_transaction_query_request(self):
        """测试 TransactionQueryRequest"""
        request = TransactionQueryRequest(
            start_date="2025-01-01",
            end_date="2025-01-31",
            transaction_type="expense",
            limit=20,
            offset=0
        )
        
        assert request.start_date == "2025-01-01"
        assert request.end_date == "2025-01-31"
        assert request.transaction_type == "expense"
        assert request.limit == 20
        assert request.offset == 0
    
    def test_transaction_query_request_limit_validation(self):
        """测试查询限制验证"""
        # limit 过大
        with pytest.raises(ValidationError):
            TransactionQueryRequest(limit=2000)
        
        # limit 为负数
        with pytest.raises(ValidationError):
            TransactionQueryRequest(limit=-1)
    
    def test_statistics_query_request(self):
        """测试 StatisticsQueryRequest"""
        request = StatisticsQueryRequest(
            start_date="2025-01-01",
            end_date="2025-01-31"
        )
        
        assert request.start_date == "2025-01-01"
        assert request.end_date == "2025-01-31"


class TestTransactionResponseDTO:
    """测试交易响应 DTO"""
    
    def test_posting_response(self):
        """测试 PostingResponse"""
        posting = PostingResponse(
            account="Expenses:Food",
            amount="50.00",
            currency="CNY"
        )
        
        assert posting.account == "Expenses:Food"
        assert posting.amount == "50.00"
        assert posting.currency == "CNY"
        assert posting.meta == {}
    
    def test_transaction_response(self):
        """测试 TransactionResponse"""
        response = TransactionResponse(
            id="txn-001",
            date="2025-01-15",
            description="午餐",
            payee="餐厅",
            flag="*",
            postings=[
                PostingResponse(account="Expenses:Food", amount="50.00", currency="CNY"),
                PostingResponse(account="Assets:Cash", amount="-50.00", currency="CNY")
            ],
            tags=["food", "lunch"],
            links=[],
            meta={},
            transaction_type="expense",
            accounts=["Expenses:Food", "Assets:Cash"],
            currencies=["CNY"]
        )
        
        assert response.id == "txn-001"
        assert response.description == "午餐"
        assert len(response.postings) == 2
        assert response.transaction_type == "expense"
        assert len(response.accounts) == 2
    
    def test_transaction_list_response(self):
        """测试 TransactionListResponse"""
        response = TransactionListResponse(
            transactions=[
                TransactionResponse(
                    id="txn-001",
                    date="2025-01-15",
                    description="午餐",
                    postings=[
                        PostingResponse(account="Expenses:Food", amount="50.00", currency="CNY"),
                        PostingResponse(account="Assets:Cash", amount="-50.00", currency="CNY")
                    ],
                    transaction_type="expense",
                    accounts=["Expenses:Food", "Assets:Cash"],
                    currencies=["CNY"]
                )
            ],
            total=1
        )
        
        assert len(response.transactions) == 1
        assert response.total == 1
    
    def test_transaction_statistics_response(self):
        """测试 TransactionStatisticsResponse"""
        response = TransactionStatisticsResponse(
            total_count=100,
            by_type={"expense": 60, "income": 30, "transfer": 10},
            by_currency={
                "CNY": {"income": 10000.0, "expense": 8000.0}
            },
            income_total={"CNY": 10000.0},
            expense_total={"CNY": 8000.0}
        )
        
        assert response.total_count == 100
        assert response.by_type["expense"] == 60
        assert response.income_total["CNY"] == 10000.0
    
    def test_validation_result_response(self):
        """测试 ValidationResultResponse"""
        response = ValidationResultResponse(
            valid=False,
            errors=["交易不平衡"]
        )
        
        assert response.valid is False
        assert len(response.errors) == 1
    
    def test_category_response(self):
        """测试 CategoryResponse"""
        response = CategoryResponse(category="Food")
        
        assert response.category == "Food"


class TestTransactionDTOSerialization:
    """测试 DTO 序列化"""
    
    def test_posting_request_to_dict(self):
        """测试 PostingRequest 转字典"""
        posting = PostingRequest(
            account="Expenses:Food",
            amount="50.00",
            currency="CNY"
        )
        
        data = posting.model_dump()
        assert data["account"] == "Expenses:Food"
        assert data["amount"] == "50.00"
        assert data["currency"] == "CNY"
    
    def test_create_transaction_request_to_dict(self):
        """测试 CreateTransactionRequest 转字典"""
        request = CreateTransactionRequest(
            date="2025-01-15",
            description="午餐",
            postings=[
                PostingRequest(account="Expenses:Food", amount="50.00", currency="CNY"),
                PostingRequest(account="Assets:Cash", amount="-50.00", currency="CNY")
            ]
        )
        
        data = request.model_dump()
        assert data["date"] == "2025-01-15"
        assert len(data["postings"]) == 2
    
    def test_transaction_response_to_json(self):
        """测试 TransactionResponse 转 JSON"""
        response = TransactionResponse(
            id="txn-001",
            date="2025-01-15",
            description="午餐",
            postings=[
                PostingResponse(account="Expenses:Food", amount="50.00", currency="CNY"),
                PostingResponse(account="Assets:Cash", amount="-50.00", currency="CNY")
            ],
            transaction_type="expense",
            accounts=["Expenses:Food", "Assets:Cash"],
            currencies=["CNY"]
        )
        
        json_str = response.model_dump_json()
        assert "txn-001" in json_str
        assert "午餐" in json_str
