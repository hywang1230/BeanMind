"""Transaction Repository 接口单元测试

测试 TransactionRepository 接口的定义和基本契约。
"""
import pytest
from abc import ABC
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from backend.domain.transaction.repositories import TransactionRepository
from backend.domain.transaction.entities import Transaction, Posting, TransactionType


class TestTransactionRepositoryInterface:
    """TransactionRepository 接口测试类"""
    
    def test_is_abstract_base_class(self):
        """测试 TransactionRepository 是抽象基类"""
        assert issubclass(TransactionRepository, ABC)
    
    def test_cannot_instantiate_directly(self):
        """测试不能直接实例化接口"""
        with pytest.raises(TypeError):
            TransactionRepository()
    
    def test_has_find_by_id_method(self):
        """测试接口定义了 find_by_id 方法"""
        assert hasattr(TransactionRepository, 'find_by_id')
        assert callable(getattr(TransactionRepository, 'find_by_id'))
    
    def test_has_find_all_method(self):
        """测试接口定义了 find_all 方法"""
        assert hasattr(TransactionRepository, 'find_all')
        assert callable(getattr(TransactionRepository, 'find_all'))
    
    def test_has_find_by_date_range_method(self):
        """测试接口定义了 find_by_date_range 方法"""
        assert hasattr(TransactionRepository, 'find_by_date_range')
        assert callable(getattr(TransactionRepository, 'find_by_date_range'))
    
    def test_has_find_by_account_method(self):
        """测试接口定义了 find_by_account 方法"""
        assert hasattr(TransactionRepository, 'find_by_account')
        assert callable(getattr(TransactionRepository, 'find_by_account'))
    
    def test_has_find_by_type_method(self):
        """测试接口定义了 find_by_type 方法"""
        assert hasattr(TransactionRepository, 'find_by_type')
        assert callable(getattr(TransactionRepository, 'find_by_type'))
    
    def test_has_find_by_tags_method(self):
        """测试接口定义了 find_by_tags 方法"""
        assert hasattr(TransactionRepository, 'find_by_tags')
        assert callable(getattr(TransactionRepository, 'find_by_tags'))
    
    def test_has_find_by_description_method(self):
        """测试接口定义了 find_by_description 方法"""
        assert hasattr(TransactionRepository, 'find_by_description')
        assert callable(getattr(TransactionRepository, 'find_by_description'))
    
    def test_has_create_method(self):
        """测试接口定义了 create 方法"""
        assert hasattr(TransactionRepository, 'create')
        assert callable(getattr(TransactionRepository, 'create'))
    
    def test_has_update_method(self):
        """测试接口定义了 update 方法"""
        assert hasattr(TransactionRepository, 'update')
        assert callable(getattr(TransactionRepository, 'update'))
    
    def test_has_delete_method(self):
        """测试接口定义了 delete 方法"""
        assert hasattr(TransactionRepository, 'delete')
        assert callable(getattr(TransactionRepository, 'delete'))
    
    def test_has_exists_method(self):
        """测试接口定义了 exists 方法"""
        assert hasattr(TransactionRepository, 'exists')
        assert callable(getattr(TransactionRepository, 'exists'))
    
    def test_has_count_method(self):
        """测试接口定义了 count 方法"""
        assert hasattr(TransactionRepository, 'count')
        assert callable(getattr(TransactionRepository, 'count'))
    
    def test_has_get_statistics_method(self):
        """测试接口定义了 get_statistics 方法"""
        assert hasattr(TransactionRepository, 'get_statistics')
        assert callable(getattr(TransactionRepository, 'get_statistics'))


class MockTransactionRepository(TransactionRepository):
    """Mock 实现，用于测试"""
    
    def __init__(self):
        self.transactions = {}
    
    def find_by_id(self, transaction_id: str):
        return self.transactions.get(transaction_id)
    
    def find_all(self, user_id=None, limit=None, offset=None):
        return list(self.transactions.values())
    
    def find_by_date_range(self, start_date, end_date, user_id=None):
        return [
            t for t in self.transactions.values()
            if start_date <= t.date <= end_date
        ]
    
    def find_by_account(self, account_name, start_date=None, end_date=None):
        return [
            t for t in self.transactions.values()
            if account_name in t.get_accounts()
        ]
    
    def find_by_type(self, transaction_type, start_date=None, end_date=None):
        return [
            t for t in self.transactions.values()
            if t.detect_transaction_type() == transaction_type
        ]
    
    def find_by_tags(self, tags, match_all=False):
        if match_all:
            return [
                t for t in self.transactions.values()
                if all(tag in t.tags for tag in tags)
            ]
        else:
            return [
                t for t in self.transactions.values()
                if any(tag in t.tags for tag in tags)
            ]
    
    def find_by_description(self, keyword, case_sensitive=False):
        if case_sensitive:
            return [
                t for t in self.transactions.values()
                if keyword in t.description
            ]
        else:
            keyword_lower = keyword.lower()
            return [
                t for t in self.transactions.values()
                if keyword_lower in t.description.lower()
            ]
    
    def create(self, transaction, user_id=None):
        if not transaction.id:
            import uuid
            transaction.id = str(uuid.uuid4())
        self.transactions[transaction.id] = transaction
        return transaction
    
    def update(self, transaction):
        if transaction.id not in self.transactions:
            raise ValueError("Transaction not found")
        self.transactions[transaction.id] = transaction
        return transaction
    
    def delete(self, transaction_id):
        if transaction_id in self.transactions:
            del self.transactions[transaction_id]
            return True
        return False
    
    def exists(self, transaction_id):
        return transaction_id in self.transactions
    
    def count(self, user_id=None, start_date=None, end_date=None):
        if start_date and end_date:
            return len(self.find_by_date_range(start_date, end_date))
        return len(self.transactions)
    
    def get_statistics(self, start_date, end_date, user_id=None):
        transactions = self.find_by_date_range(start_date, end_date)
        by_type = {}
        for t in transactions:
            t_type = t.detect_transaction_type().value
            by_type[t_type] = by_type.get(t_type, 0) + 1
        
        return {
            "total_count": len(transactions),
            "by_type": by_type,
            "by_currency": {},
            "income_total": {},
            "expense_total": {}
        }


class TestTransactionRepositoryMock:
    """测试 Mock 实现的基本功能"""
    
    @pytest.fixture
    def repository(self):
        """创建 Mock Repository"""
        return MockTransactionRepository()
    
    @pytest.fixture
    def sample_transaction(self):
        """创建示例交易"""
        return Transaction(
            id="txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
    
    def test_mock_implements_interface(self, repository):
        """测试 Mock 实现了接口"""
        assert isinstance(repository, TransactionRepository)
    
    def test_create_transaction(self, repository, sample_transaction):
        """测试创建交易"""
        result = repository.create(sample_transaction)
        assert result.id is not None
        assert result.description == "午餐"
    
    def test_find_by_id(self, repository, sample_transaction):
        """测试按 ID 查找"""
        repository.create(sample_transaction)
        found = repository.find_by_id("txn-001")
        assert found is not None
        assert found.id == "txn-001"
    
    def test_find_by_id_not_found(self, repository):
        """测试按 ID 查找（不存在）"""
        found = repository.find_by_id("non-existent")
        assert found is None
    
    def test_find_all(self, repository):
        """测试查找所有交易"""
        # 创建多个交易
        for i in range(3):
            txn = Transaction(
                id=f"txn-{i:03d}",
                date=date(2025, 1, i+1),
                description=f"交易 {i}",
                postings=[
                    Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                    Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
                ]
            )
            repository.create(txn)
        
        all_transactions = repository.find_all()
        assert len(all_transactions) == 3
    
    def test_find_by_date_range(self, repository):
        """测试按日期范围查找"""
        # 创建不同日期的交易
        dates = [date(2025, 1, 1), date(2025, 1, 15), date(2025, 1, 31)]
        for i, d in enumerate(dates):
            txn = Transaction(
                id=f"txn-{i:03d}",
                date=d,
                description=f"交易 {i}",
                postings=[
                    Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                    Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
                ]
            )
            repository.create(txn)
        
        # 查找 1月1日到1月15日
        results = repository.find_by_date_range(date(2025, 1, 1), date(2025, 1, 15))
        assert len(results) == 2
    
    def test_find_by_account(self, repository):
        """测试按账户查找"""
        txn1 = Transaction(
            id="txn-001",
            date=date(2025, 1, 1),
            description="食物",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        txn2 = Transaction(
            id="txn-002",
            date=date(2025, 1, 2),
            description="交通",
            postings=[
                Posting(account="Expenses:Transport", amount=Decimal("10"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-10"), currency="CNY")
            ]
        )
        
        repository.create(txn1)
        repository.create(txn2)
        
        results = repository.find_by_account("Expenses:Food")
        assert len(results) == 1
        assert results[0].id == "txn-001"
    
    def test_find_by_type(self, repository):
        """测试按类型查找"""
        expense_txn = Transaction(
            id="txn-expense",
            date=date(2025, 1, 1),
            description="支出",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        income_txn = Transaction(
            id="txn-income",
            date=date(2025, 1, 2),
            description="收入",
            postings=[
                Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
                Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY")
            ]
        )
        
        repository.create(expense_txn)
        repository.create(income_txn)
        
        expense_results = repository.find_by_type(TransactionType.EXPENSE)
        assert len(expense_results) == 1
        assert expense_results[0].id == "txn-expense"
    
    def test_find_by_tags(self, repository):
        """测试按标签查找"""
        txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 1),
            description="午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ],
            tags={"food", "lunch"}
        )
        repository.create(txn)
        
        results = repository.find_by_tags(["lunch"])
        assert len(results) == 1
        assert results[0].id == "txn-001"
    
    def test_find_by_description(self, repository):
        """测试按描述搜索"""
        txn = Transaction(
            id="txn-001",
            date=date(2025, 1, 1),
            description="麦当劳午餐",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        repository.create(txn)
        
        results = repository.find_by_description("午餐")
        assert len(results) == 1
        
        # 测试不区分大小写
        results = repository.find_by_description("MCDON", case_sensitive=False)
        assert len(results) == 0  # 中文描述
    
    def test_update_transaction(self, repository, sample_transaction):
        """测试更新交易"""
        repository.create(sample_transaction)
        
        sample_transaction.description = "更新的描述"
        updated = repository.update(sample_transaction)
        
        assert updated.description == "更新的描述"
    
    def test_update_nonexistent_transaction(self, repository):
        """测试更新不存在的交易"""
        txn = Transaction(
            id="non-existent",
            date=date(2025, 1, 1),
            description="测试",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        
        with pytest.raises(ValueError, match="Transaction not found"):
            repository.update(txn)
    
    def test_delete_transaction(self, repository, sample_transaction):
        """测试删除交易"""
        repository.create(sample_transaction)
        
        result = repository.delete("txn-001")
        assert result is True
        assert repository.find_by_id("txn-001") is None
    
    def test_delete_nonexistent_transaction(self, repository):
        """测试删除不存在的交易"""
        result = repository.delete("non-existent")
        assert result is False
    
    def test_exists(self, repository, sample_transaction):
        """测试检查交易是否存在"""
        assert repository.exists("txn-001") is False
        
        repository.create(sample_transaction)
        assert repository.exists("txn-001") is True
    
    def test_count(self, repository):
        """测试统计交易数量"""
        assert repository.count() == 0
        
        for i in range(5):
            txn = Transaction(
                id=f"txn-{i:03d}",
                date=date(2025, 1, i+1),
                description=f"交易 {i}",
                postings=[
                    Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                    Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
                ]
            )
            repository.create(txn)
        
        assert repository.count() == 5
    
    def test_get_statistics(self, repository):
        """测试获取统计信息"""
        # 创建不同类型的交易
        expense_txn = Transaction(
            id="txn-expense",
            date=date(2025, 1, 1),
            description="支出",
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ]
        )
        income_txn = Transaction(
            id="txn-income",
            date=date(2025, 1, 2),
            description="收入",
            postings=[
                Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
                Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY")
            ]
        )
        
        repository.create(expense_txn)
        repository.create(income_txn)
        
        stats = repository.get_statistics(date(2025, 1, 1), date(2025, 1, 31))
        
        assert stats["total_count"] == 2
        assert stats["by_type"]["expense"] == 1
        assert stats["by_type"]["income"] == 1
