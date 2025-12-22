"""TransactionService 单元测试

测试 TransactionService 的所有功能。
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from backend.domain.transaction.entities import Transaction, Posting, TransactionType
from backend.domain.transaction.services import TransactionService
from backend.domain.transaction.repositories import TransactionRepository
from backend.domain.account.repositories import AccountRepository


class TestTransactionService:
    """TransactionService 测试类"""
    
    @pytest.fixture
    def mock_transaction_repository(self):
        """创建 Mock Transaction Repository"""
        repo = Mock(spec=TransactionRepository)
        repo.create = Mock(return_value=None)
        repo.get_statistics = Mock(return_value={})
        repo.find_by_date_range = Mock(return_value=[])
        return repo
    
    @pytest.fixture
    def mock_account_repository(self):
        """创建 Mock Account Repository"""
        repo = Mock(spec=AccountRepository)
        repo.exists = Mock(return_value=True)  # 默认账户都存在
        repo.get_balance = Mock(return_value={"CNY": Decimal("1000")})
        return repo
    
    @pytest.fixture
    def service(self, mock_transaction_repository, mock_account_repository):
        """创建 Service 实例"""
        return TransactionService(mock_transaction_repository, mock_account_repository)
    
    @pytest.fixture
    def valid_postings(self):
        """创建有效的记账分录"""
        return [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
    
    def test_create_transaction_success(self, service, valid_postings, mock_transaction_repository):
        """测试成功创建交易"""
        service.create_transaction(
            txn_date=date(2025, 1, 15),
            description="午餐",
            postings=valid_postings,
            user_id="user-001"
        )
        
        # 验证 repository.create 被调用
        mock_transaction_repository.create.assert_called_once()
    
    def test_create_transaction_empty_description(self, service, valid_postings, mock_transaction_repository):
        """测试创建交易（空描述，应该成功）"""
        service.create_transaction(
            txn_date=date(2025, 1, 15),
            description="",
            postings=valid_postings
        )
        
        # 验证 repository.create 被调用（空描述应该可以正常创建）
        mock_transaction_repository.create.assert_called_once()
    
    def test_create_transaction_insufficient_postings(self, service):
        """测试创建交易（记账分录不足）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY")
        ]
        
        with pytest.raises(ValueError, match="至少需要两个记账分录"):
            service.create_transaction(
                txn_date=date(2025, 1, 15),
                description="测试",
                postings=postings
            )
    
    def test_create_transaction_zero_amount(self, service):
        """测试创建交易（金额为零）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("0"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("0"), currency="CNY")
        ]
        
        with pytest.raises(ValueError, match="金额不能为零"):
            service.create_transaction(
                txn_date=date(2025, 1, 15),
                description="测试",
                postings=postings
            )
    
    def test_create_transaction_unbalanced(self, service):
        """测试创建交易（不平衡）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-40"), currency="CNY")  # 不平衡
        ]
        
        with pytest.raises(ValueError, match="交易不平衡"):
            service.create_transaction(
                txn_date=date(2025, 1, 15),
                description="测试",
                postings=postings
            )
    
    def test_create_transaction_account_not_exist(self, service, mock_account_repository):
        """测试创建交易（账户不存在）"""
        mock_account_repository.exists = Mock(return_value=False)
        
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
        ]
        
        with pytest.raises(ValueError, match="账户.*不存在"):
            service.create_transaction(
                txn_date=date(2025, 1, 15),
                description="测试",
                postings=postings
            )
    
    def test_validate_balance_success(self, service, valid_postings):
        """测试验证借贷平衡（成功）"""
        service._validate_balance(valid_postings)
        # 不应抛出异常
    
    def test_validate_balance_multi_currency(self, service):
        """测试验证借贷平衡（多货币）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Expenses:Shopping", amount=Decimal("10"), currency="USD"),
            Posting(account="Assets:Cash:CNY", amount=Decimal("-50"), currency="CNY"),
            Posting(account="Assets:Cash:USD", amount=Decimal("-10"), currency="USD")
        ]
        
        service._validate_balance(postings)
        # 不应抛出异常
    
    def test_validate_balance_unbalanced_multi_currency(self, service):
        """测试验证借贷平衡（多货币不平衡）"""
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Expenses:Shopping", amount=Decimal("10"), currency="USD"),
            Posting(account="Assets:Cash:CNY", amount=Decimal("-50"), currency="CNY"),
            Posting(account="Assets:Cash:USD", amount=Decimal("-5"), currency="USD")  # 不平衡
        ]
        
        with pytest.raises(ValueError, match="交易不平衡"):
            service._validate_balance(postings)
    
    def test_validate_transaction_success(self, service):
        """测试验证交易（成功）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        assert service.validate_transaction(transaction) is True
    
    def test_detect_transaction_type_expense(self, service):
        """测试检测交易类型（支出）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        assert service.detect_transaction_type(transaction) == TransactionType.EXPENSE
    
    def test_detect_transaction_type_income(self, service):
        """测试检测交易类型（收入）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="工资",
            postings=[
                Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
                Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY")
            ]
        )
        
        assert service.detect_transaction_type(transaction) == TransactionType.INCOME
    
    def test_detect_transaction_type_transfer(self, service):
        """测试检测交易类型（转账）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="转账",
            postings=[
                Posting(account="Assets:Bank:Checking", amount=Decimal("1000"), currency="CNY"),
                Posting(account="Assets:Bank:Savings", amount=Decimal("-1000"), currency="CNY")
            ]
        )
        
        assert service.detect_transaction_type(transaction) == TransactionType.TRANSFER
    
    def test_is_balanced_true(self, service):
        """测试判断平衡（平衡）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        assert service.is_balanced(transaction) is True
    
    def test_is_balanced_false(self, service):
        """测试判断平衡（不平衡）"""
        # 创建不平衡的交易（绕过实体验证）
        postings = [
            Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-40"), currency="CNY")
        ]
        
        assert service.is_balanced(
            Mock(postings=postings)
        ) is False
    
    def test_get_involved_accounts(self, service):
        """测试获取涉及的账户"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        accounts = service.get_involved_accounts(transaction)
        assert "Expenses:Food" in accounts
        assert "Assets:Cash" in accounts
    
    def test_calculate_transaction_amount(self, service):
        """测试计算交易金额"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        amount = service.calculate_transaction_amount(transaction, "CNY")
        assert amount == Decimal("50")  # 100 / 2
    
    def test_validate_account_balance_sufficient(self, service, mock_account_repository):
        """测试验证账户余额充足"""
        mock_account_repository.get_balance.return_value = {"CNY": Decimal("1000")}
        
        result = service.validate_account_balance_sufficient(
            "Assets:Cash",
            Decimal("500"),
            "CNY"
        )
        
        assert result is True
    
    def test_validate_account_balance_insufficient(self, service, mock_account_repository):
        """测试验证账户余额不足"""
        mock_account_repository.get_balance.return_value = {"CNY": Decimal("100")}
        
        result = service.validate_account_balance_sufficient(
            "Assets:Cash",
            Decimal("500"),
            "CNY"
        )
        
        assert result is False
    
    def test_get_transaction_summary(self, service, mock_transaction_repository):
        """测试获取交易摘要"""
        mock_transaction_repository.get_statistics.return_value = {
            "total_count": 10,
            "by_type": {"expense": 6, "income": 4}
        }
        
        summary = service.get_transaction_summary(
            date(2025, 1, 1),
            date(2025, 1, 31),
            user_id="user-001"
        )
        
        assert summary["total_count"] == 10
        mock_transaction_repository.get_statistics.assert_called_once()
    
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
        
        # Mock 返回相似的交易
        similar_txn = Transaction(
            id="txn-002",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        mock_transaction_repository.find_by_date_range.return_value = [similar_txn]
        
        duplicates = service.find_duplicate_transactions(transaction)
        
        assert len(duplicates) == 1
        assert duplicates[0].id == "txn-002"
    
    def test_categorize_transaction_expense(self, service):
        """测试交易分类（支出）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food:Dining", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        category = service.categorize_transaction(transaction)
        assert category == "Food"
    
    def test_categorize_transaction_income(self, service):
        """测试交易分类（收入）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="工资",
            postings=[
                Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
                Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY")
            ]
        )
        
        category = service.categorize_transaction(transaction)
        assert category == "Salary"
    
    def test_categorize_transaction_transfer(self, service):
        """测试交易分类（转账）"""
        transaction = Transaction(
            date=date(2025, 1, 15),
            description="转账",
            postings=[
                Posting(account="Assets:Bank:Checking", amount=Decimal("1000"), currency="CNY"),
                Posting(account="Assets:Bank:Savings", amount=Decimal("-1000"), currency="CNY")
            ]
        )
        
        category = service.categorize_transaction(transaction)
        assert category == "Transfer"
