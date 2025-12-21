"""TransactionApplicationService 单元测试

测试交易应用服务的所有功能。
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from backend.application.services import TransactionApplicationService
from backend.domain.transaction.entities import Transaction, Posting, TransactionType
from backend.domain.transaction.repositories import TransactionRepository
from backend.domain.account.repositories import AccountRepository


class TestTransactionApplicationService:
    """TransactionApplicationService 测试类"""
    
    @pytest.fixture
    def mock_transaction_repository(self):
        """创建 Mock Transaction Repository"""
        repo = Mock(spec=TransactionRepository)
        repo.create = Mock(return_value=None)
        repo.find_by_id = Mock(return_value=None)
        repo.find_all = Mock(return_value=[])
        repo.find_by_date_range = Mock(return_value=[])
        repo.find_by_account = Mock(return_value=[])
        repo.find_by_type = Mock(return_value=[])
        repo.find_by_tags = Mock(return_value=[])
        repo.find_by_description = Mock(return_value=[])
        repo.update = Mock(return_value=None)
        repo.delete = Mock(return_value=True)
        repo.get_statistics = Mock(return_value={})
        return repo
    
    @pytest.fixture
    def mock_account_repository(self):
        """创建 Mock Account Repository"""
        repo = Mock(spec=AccountRepository)
        repo.exists = Mock(return_value=True)
        repo.get_balance = Mock(return_value={"CNY": Decimal("1000")})
        return repo
    
    @pytest.fixture
    def service(self, mock_transaction_repository, mock_account_repository):
        """创建 Service 实例"""
        return TransactionApplicationService(
            mock_transaction_repository,
            mock_account_repository
        )
    
    @pytest.fixture
    def sample_posting_dto(self):
        """创建示例记账分录 DTO"""
        return {
            "account": "Expenses:Food",
            "amount": "50.00",
            "currency": "CNY"
        }
    
    @pytest.fixture
    def sample_transaction_dto(self, sample_posting_dto):
        """创建示例交易 DTO"""
        return {
            "date": "2025-01-15",
            "description": "午餐",
            "postings": [
                sample_posting_dto,
                {
                    "account": "Assets:Cash",
                    "amount": "-50.00",
                    "currency": "CNY"
                }
            ]
        }
    
    def test_create_transaction(self, service, sample_transaction_dto, mock_transaction_repository):
        """测试创建交易"""
        # Mock repository.create 返回一个交易
        created_txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.create.return_value = created_txn
        
        result = service.create_transaction(
            txn_date=sample_transaction_dto["date"],
            description=sample_transaction_dto["description"],
            postings=sample_transaction_dto["postings"]
        )
        
        assert result["id"] == "txn-001"
        assert result["description"] == "午餐"
        assert len(result["postings"]) == 2
        mock_transaction_repository.create.assert_called_once()
    
    def test_get_transaction_by_id_exists(self, service, mock_transaction_repository):
        """测试根据 ID 获取交易（存在）"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_id.return_value = transaction
        
        result = service.get_transaction_by_id("txn-001")
        
        assert result is not None
        assert result["id"] == "txn-001"
        assert result["description"] == "午餐"
    
    def test_get_transaction_by_id_not_exists(self, service, mock_transaction_repository):
        """测试根据 ID 获取交易（不存在）"""
        mock_transaction_repository.find_by_id.return_value = None
        
        result = service.get_transaction_by_id("non-existent")
        
        assert result is None
    
    def test_get_transactions_by_date_range(self, service, mock_transaction_repository):
        """测试按日期范围获取交易"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_date_range.return_value = [transaction]
        
        results = service.get_transactions(
            start_date="2025-01-01",
            end_date="2025-01-31"
        )
        
        assert len(results) == 1
        assert results[0]["id"] == "txn-001"
        mock_transaction_repository.find_by_date_range.assert_called_once()
    
    def test_get_transactions_by_account(self, service, mock_transaction_repository):
        """测试按账户获取交易"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_account.return_value = [transaction]
        
        results = service.get_transactions(account="Expenses:Food")
        
        assert len(results) == 1
        assert results[0]["id"] == "txn-001"
        mock_transaction_repository.find_by_account.assert_called_once()
    
    def test_get_transactions_by_type(self, service, mock_transaction_repository):
        """测试按类型获取交易"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_type.return_value = [transaction]
        
        results = service.get_transactions(transaction_type="expense")
        
        assert len(results) == 1
        mock_transaction_repository.find_by_type.assert_called_once()
    
    def test_get_transactions_all(self, service, mock_transaction_repository):
        """测试获取所有交易"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_all.return_value = [transaction]
        
        results = service.get_transactions(limit=10)
        
        assert len(results) == 1
        mock_transaction_repository.find_all.assert_called_once()
    
    def test_update_transaction(self, service, mock_transaction_repository):
        """测试更新交易"""
        # Mock find_by_id 返回现有交易
        existing_txn = Transaction(
            id="txn-001",
            date=date(2025, 1,15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_id.return_value = existing_txn
        
        # Mock update 返回更新后的交易
        updated_txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="更新的描述",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.update.return_value = updated_txn
        
        result = service.update_transaction(
            transaction_id="txn-001",
            description="更新的描述"
        )
        
        assert result["description"] == "更新的描述"
        mock_transaction_repository.update.assert_called_once()
    
    def test_update_transaction_not_exists(self, service, mock_transaction_repository):
        """测试更新不存在的交易"""
        mock_transaction_repository.find_by_id.return_value = None
        
        with pytest.raises(ValueError, match="不存在"):
            service.update_transaction(
                transaction_id="non-existent",
                description="测试"
            )
    
    def test_delete_transaction(self, service, mock_transaction_repository):
        """测试删除交易"""
        mock_transaction_repository.delete.return_value = True
        
        result = service.delete_transaction("txn-001")
        
        assert result is True
        mock_transaction_repository.delete.assert_called_once_with("txn-001")
    
    def test_get_statistics(self, service, mock_transaction_repository):
        """测试获取统计信息"""
        stats = {
            "total_count": 10,
            "by_type": {"expense": 6, "income": 4}
        }
        mock_transaction_repository.get_statistics.return_value = stats
        
        result = service.get_statistics("2025-01-01", "2025-01-31")
        
        assert result["total_count"] == 10
        mock_transaction_repository.get_statistics.assert_called_once()
    
    def test_validate_transaction_valid(self, service, sample_transaction_dto):
        """测试验证交易（有效）"""
        result = service.validate_transaction(sample_transaction_dto)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_transaction_invalid(self, service):
        """测试验证交易（无效）"""
        invalid_dto = {
            "date": "2025-01-15",
            "description": "测试",
            "postings": [
                {"account": "Expenses:Food", "amount": "50", "currency": "CNY"}
                # 缺少第二个 posting
            ]
        }
        
        result = service.validate_transaction(invalid_dto)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_categorize_transaction(self, service, mock_transaction_repository):
        """测试交易分类"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food:Dining", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        mock_transaction_repository.find_by_id.return_value = transaction
        
        category = service.categorize_transaction("txn-001")
        
        assert category == "Food"
    
    def test_find_duplicate_transactions(self, service, mock_transaction_repository):
        """测试查找重复交易"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        duplicate = Transaction(
            id="txn-002",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        # Mock find_by_id 返回原交易
        mock_transaction_repository.find_by_id.return_value = transaction
        
        # Mock find_by_date_range 返回重复交易
        mock_transaction_repository.find_by_date_range.return_value = [duplicate]
        
        results = service.find_duplicate_transactions("txn-001")
        
        assert len(results) == 1
        assert results[0]["id"] == "txn-002"
    
    def test_posting_to_dto(self, service):
        """测试 Posting 转 DTO"""
        posting = Posting(
            account="Expenses:Food",
            amount=Decimal("50.00"),
            currency="CNY"
        )
        
        dto = service._posting_to_dto(posting)
        
        assert dto["account"] == "Expenses:Food"
        assert dto["amount"] == "50.00"
        assert dto["currency"] == "CNY"
    
    def test_dto_to_posting(self, service, sample_posting_dto):
        """测试 DTO 转 Posting"""
        posting = service._dto_to_posting(sample_posting_dto)
        
        assert posting.account == "Expenses:Food"
        assert posting.amount == Decimal("50.00")
        assert posting.currency == "CNY"
    
    def test_transaction_to_dto(self, service):
        """测试 Transaction 转 DTO"""
        transaction = Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ],
            tags={"food", "lunch"}
        )
        
        dto = service._transaction_to_dto(transaction)
        
        assert dto["id"] == "txn-001"
        assert dto["description"] == "午餐"
        assert len(dto["postings"]) == 2
        assert "food" in dto["tags"]
        assert dto["transaction_type"] == "expense"
