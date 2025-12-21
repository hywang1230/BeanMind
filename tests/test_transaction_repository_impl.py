"""TransactionRepositoryImpl 单元测试

测试 TransactionRepositoryImpl 的所有功能。
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path

from beancount.core.data import Transaction as BeancountTransaction, Posting as BeancountPosting
from beancount.core import amount

from backend.domain.transaction.entities import Transaction, Posting, TransactionType, TransactionFlag
from backend.domain.transaction.repositories import TransactionRepository
from backend.infrastructure.persistence.beancount.repositories import TransactionRepositoryImpl
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.db.models import TransactionMetadata


class TestTransactionRepositoryImpl:
    """TransactionRepositoryImpl 测试类"""
    
    @pytest.fixture
    def mock_beancount_service(self):
        """创建 Mock Beancount Service"""
        service = Mock(spec=BeancountService)
        service.ledger_path = Path("/tmp/test.beancount")
        service.entries = []
        service.reload = Mock()
        return service
    
    @pytest.fixture
    def mock_db_session(self):
        """创建 Mock 数据库会话"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.query = Mock()
        return session
    
    @pytest.fixture
    def repository(self, mock_beancount_service, mock_db_session):
        """创建 Repository 实例"""
        return TransactionRepositoryImpl(mock_beancount_service, mock_db_session)
    
    @pytest.fixture
    def sample_beancount_transaction(self):
        """创建示例 Beancount 交易"""
        postings = [
            BeancountPosting(
                account="Expenses:Food",
                units=amount.Amount(Decimal("50"), "CNY"),
                cost=None,
                price=None,
                flag=None,
                meta={}
            ),
            BeancountPosting(
                account="Assets:Cash",
                units=amount.Amount(Decimal("-50"), "CNY"),
                cost=None,
                price=None,
                flag=None,
                meta={}
            )
        ]
        
        return BeancountTransaction(
            meta={},
            date=date(2025, 1, 15),
            flag="*",
            payee="餐厅",
            narration="午餐",
            tags=set(),
            links=set(),
            postings=postings
        )
    
    @pytest.fixture
    def sample_domain_transaction(self):
        """创建示例领域交易"""
        return Transaction(
            id="test-txn-001",
            date=date(2025, 1, 15),
            description="午餐",
            payee="餐厅",
            flag=TransactionFlag.CLEARED,
            postings=[
                Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
            ],
            tags=set(),
            links=set(),
            meta={}
        )
    
    def test_implements_repository_interface(self, repository):
        """测试实现了 Repository 接口"""
        assert isinstance(repository, TransactionRepository)
    
    def test_initialization(self, mock_beancount_service, mock_db_session):
        """测试初始化"""
        repo = TransactionRepositoryImpl(mock_beancount_service, mock_db_session)
        assert repo.beancount_service == mock_beancount_service
        assert repo.db_session == mock_db_session
        assert isinstance(repo._transactions_cache, dict)
    
    def test_load_transactions(self, mock_beancount_service, mock_db_session, sample_beancount_transaction):
        """测试加载交易"""
        mock_beancount_service.entries = [sample_beancount_transaction]
        
        repo = TransactionRepositoryImpl(mock_beancount_service, mock_db_session)
        
        assert len(repo._transactions_cache) == 1
    
    def test_beancount_to_domain_conversion(self, repository, sample_beancount_transaction):
        """测试 Beancount 到领域实体的转换"""
        transaction = repository._beancount_to_domain(sample_beancount_transaction)
        
        assert isinstance(transaction, Transaction)
        assert transaction.date == date(2025, 1, 15)
        assert transaction.description == "午餐"
        assert transaction.payee == "餐厅"
        assert transaction.flag == TransactionFlag.CLEARED
        assert len(transaction.postings) == 2
    
    def test_domain_to_beancount_conversion(self, repository, sample_domain_transaction):
        """测试领域实体到 Beancount 的转换"""
        beancount_txn = repository._domain_to_beancount(sample_domain_transaction)
        
        assert isinstance(beancount_txn, BeancountTransaction)
        assert beancount_txn.date == date(2025, 1,15)
        assert beancount_txn.narration == "午餐"
        assert beancount_txn.payee == "餐厅"
        assert beancount_txn.flag == "*"
        assert len(beancount_txn.postings) == 2
    
    def test_generate_transaction_id(self, repository):
        """测试生成交易 ID"""
        txn_id = repository._generate_transaction_id(date(2025, 1, 15), "午餐")
        
        assert isinstance(txn_id, str)
        assert len(txn_id) > 0
    
    def test_find_by_id_exists(self, repository, sample_domain_transaction):
        """测试按 ID 查找（存在）"""
        repository._transactions_cache[sample_domain_transaction.id] = sample_domain_transaction
        
        found = repository.find_by_id(sample_domain_transaction.id)
        
        assert found is not None
        assert found.id == sample_domain_transaction.id
    
    def test_find_by_id_not_exists(self, repository):
        """测试按 ID 查找（不存在）"""
        found = repository.find_by_id("non-existent")
        assert found is None
    
    def test_find_all(self, repository):
        """测试查找所有交易"""
        # 添加多个交易
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
            repository._transactions_cache[txn.id] = txn
        
        all_txns = repository.find_all()
        assert len(all_txns) == 3
    
    def test_find_all_with_pagination(self, repository):
        """测试分页查找"""
        # 添加多个交易
        for i in range(10):
            txn = Transaction(
                id=f"txn-{i:03d}",
                date=date(2025, 1, i+1),
                description=f"交易 {i}",
                postings=[
                    Posting(account="Expenses:Food", amount=Decimal("50"), currency="CNY"),
                    Posting(account="Assets:Cash", amount=Decimal("-50"), currency="CNY")
                ]
            )
            repository._transactions_cache[txn.id] = txn
        
        # 测试 limit
        limited = repository.find_all(limit=5)
        assert len(limited) == 5
        
        # 测试 offset
        offset_txns = repository.find_all(offset=5)
        assert len(offset_txns) == 5
    
    def test_find_by_date_range(self, repository):
        """测试按日期范围查找"""
        # 添加不同日期的交易
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
            repository._transactions_cache[txn.id] = txn
        
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
        
        repository._transactions_cache[txn1.id] = txn1
        repository._transactions_cache[txn2.id] = txn2
        
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
        
        repository._transactions_cache[expense_txn.id] = expense_txn
        repository._transactions_cache[income_txn.id] = income_txn
        
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
        repository._transactions_cache[txn.id] = txn
        
        results = repository.find_by_tags(["lunch"])
        assert len(results) == 1
    
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
        repository._transactions_cache[txn.id] = txn
        
        results = repository.find_by_description("午餐")
        assert len(results) == 1
    
    @patch("builtins.open", new_callable=mock_open)
    def test_create_transaction(self, mock_file, repository, sample_domain_transaction):
        """测试创建交易"""
        # 模拟文件写入
        sample_domain_transaction.id = None  # 测试 ID 生成
        
        result = repository.create(sample_domain_transaction, user_id="user-001")
        
        # 验证文件写入被调用
        mock_file.assert_called()
        
        # 验证 reload 被调用
        repository.beancount_service.reload.assert_called()
    
    def test_update_transaction(self, repository, sample_domain_transaction):
        """测试更新交易"""
        repository._transactions_cache[sample_domain_transaction.id] = sample_domain_transaction
        
        sample_domain_transaction.description = "更新的描述"
        updated = repository.update(sample_domain_transaction)
        
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
        
        with pytest.raises(ValueError, match="不存在"):
            repository.update(txn)
    
    def test_delete_transaction(self, repository, sample_domain_transaction):
        """测试删除交易"""
        repository._transactions_cache[sample_domain_transaction.id] = sample_domain_transaction
        
        result = repository.delete(sample_domain_transaction.id)
        
        assert result is True
        assert sample_domain_transaction.id not in repository._transactions_cache
    
    def test_delete_nonexistent_transaction(self, repository):
        """测试删除不存在的交易"""
        result = repository.delete("non-existent")
        assert result is False
    
    def test_exists(self, repository, sample_domain_transaction):
        """测试检查交易是否存在"""
        assert repository.exists(sample_domain_transaction.id) is False
        
        repository._transactions_cache[sample_domain_transaction.id] = sample_domain_transaction
        assert repository.exists(sample_domain_transaction.id) is True
    
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
            repository._transactions_cache[txn.id] = txn
        
        assert repository.count() == 5
    
    def test_get_statistics(self, repository):
        """测试获取统计信息"""
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
        
        repository._transactions_cache[expense_txn.id] = expense_txn
        repository._transactions_cache[income_txn.id] = income_txn
        
        stats = repository.get_statistics(date(2025, 1, 1), date(2025, 1, 31))
        
        assert stats["total_count"] == 2
        assert stats["by_type"]["expense"] == 1
        assert stats["by_type"]["income"] == 1
        assert "CNY" in stats["by_currency"]
    
    def test_reload(self, repository):
        """测试重新加载"""
        repository.reload()
        
        repository.beancount_service.reload.assert_called()
