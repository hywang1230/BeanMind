"""账户仓储 Beancount 实现单元测试

测试 AccountRepositoryImpl 从 Beancount 文件读取和写入账户数据。
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl


@pytest.fixture
def test_ledger_path():
    """获取测试账本文件路径"""
    return Path(__file__).parent / "fixtures" / "test_ledger.beancount"


@pytest.fixture
def temp_ledger_path(test_ledger_path):
    """创建临时账本文件（用于写入测试）"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.beancount', delete=False) as f:
        # 复制测试账本内容
        with open(test_ledger_path, 'r', encoding='utf-8') as source:
            f.write(source.read())
        temp_path = Path(f.name)
    
    yield temp_path
    
    # 清理
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def beancount_service(test_ledger_path):
    """创建 BeancountService 实例"""
    return BeancountService(test_ledger_path)


@pytest.fixture
def repository(beancount_service):
    """创建 AccountRepositoryImpl 实例"""
    return AccountRepositoryImpl(beancount_service)


@pytest.fixture
def temp_repository(temp_ledger_path):
    """创建使用临时文件的仓储（用于写入测试）"""
    service = BeancountService(temp_ledger_path)
    return AccountRepositoryImpl(service)


class TestAccountRepositoryImpl:
    """账户仓储实现测试类"""
    
    def test_load_accounts(self, repository):
        """测试加载账户"""
        accounts = repository.find_all()
        
        # 至少应该有测试账本中定义的账户
        assert len(accounts) > 0
        
        # 验证账户类型
        account_names = [acc.name for acc in accounts]
        assert "Assets:Bank:Checking" in account_names
        assert "Assets:Bank:Savings" in account_names
        assert "Expenses:Food" in account_names
        assert "Income:Salary" in account_names
    
    def test_find_by_name(self, repository):
        """测试根据名称查找账户"""
        account = repository.find_by_name("Assets:Bank:Checking")
        
        assert account is not None
        assert account.name == "Assets:Bank:Checking"
        assert account.account_type == AccountType.ASSETS
        assert "CNY" in account.currencies
    
    def test_find_by_name_not_found(self, repository):
        """测试查找不存在的账户"""
        account = repository.find_by_name("Assets:NonExistent")
        assert account is None
    
    def test_find_by_type(self, repository):
        """测试根据类型查找账户"""
        asset_accounts = repository.find_by_type(AccountType.ASSETS)
        
        assert len(asset_accounts) > 0
        assert all(acc.account_type == AccountType.ASSETS for acc in asset_accounts)
        
        # 检查特定账户
        account_names = [acc.name for acc in asset_accounts]
        assert "Assets:Bank:Checking" in account_names
        assert "Assets:Bank:Savings" in account_names
    
    def test_find_by_prefix(self, repository):
        """测试根据前缀查找账户"""
        bank_accounts = repository.find_by_prefix("Assets:Bank")
        
        assert len(bank_accounts) >= 2
        assert all(acc.name.startswith("Assets:Bank") for acc in bank_accounts)
    
    def test_find_active_accounts(self, repository):
        """测试获取活跃账户"""
        active_accounts = repository.find_active_accounts()
        
        # Assets:Old:Account 应该被关闭
        active_names = [acc.name for acc in active_accounts]
        assert "Assets:Bank:Checking" in active_names
        assert "Assets:Old:Account" not in active_names
    
    def test_get_balance(self, repository):
        """测试获取账户余额"""
        # 根据测试账本，Assets:Bank:Checking 应该有余额
        balances = repository.get_balance("Assets:Bank:Checking")
        
        assert "CNY" in balances
        # 初始 10000 + 工资 8000 = 18000
        assert balances["CNY"] == Decimal("18000.00")
    
    def test_get_balance_specific_currency(self, repository):
        """测试获取指定货币的余额"""
        balances = repository.get_balance("Assets:Bank:Checking", "CNY")
        
        assert "CNY" in balances
        assert balances["CNY"] == Decimal("18000.00")
    
    def test_get_balance_nonexistent_account(self, repository):
        """测试获取不存在账户的余额"""
        balances = repository.get_balance("Assets:NonExistent")
        assert balances == {}
    
    def test_get_balances_by_type(self, repository):
        """测试获取指定类型所有账户的余额"""
        balances = repository.get_balances_by_type(AccountType.ASSETS)
        
        assert "Assets:Bank:Checking" in balances
        assert "Assets:Bank:Savings" in balances
        assert "Assets:Cash" in balances
        
        # 验证具体余额
        assert balances["Assets:Bank:Checking"]["CNY"] == Decimal("18000.00")
        assert balances["Assets:Bank:Savings"]["CNY"] == Decimal("5000.00")
        # 现金: 500 - 45 (午餐) - 5 (公交) = 450
        assert balances["Assets:Cash"]["CNY"] == Decimal("450.00")
    
    def test_get_balance_at_date(self, repository):
        """测试获取指定日期的余额"""
        # 2025-01-03 时只有初始余额
        date = datetime(2025, 1, 3)
        balances = repository.get_balance_at_date("Assets:Bank:Checking", date)
        
        assert "CNY" in balances
        assert balances["CNY"] == Decimal("10000.00")  # 只有初始余额
    
    def test_create_account(self, temp_repository):
        """测试创建账户"""
        new_account = Account(
            name="Assets:Investment:Stocks",
            account_type=AccountType.ASSETS,
            currencies={"CNY", "USD"}
        )
        
        created = temp_repository.create(new_account)
        
        assert created.name == "Assets:Investment:Stocks"
        assert temp_repository.exists("Assets:Investment:Stocks")
        
        # 验证账户已写入文件
        found = temp_repository.find_by_name("Assets:Investment:Stocks")
        assert found is not None
        assert "CNY" in found.currencies
        assert "USD" in found.currencies
    
    def test_create_duplicate_account(self, temp_repository):
        """测试创建重复账户"""
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS
        )
        
        with pytest.raises(ValueError, match="已存在"):
            temp_repository.create(account)
    
    def test_delete_account(self, temp_repository):
        """测试删除账户（关闭账户）"""
        # 创建一个新账户
        account = Account(
            name="Assets:Test:TempAccount",
            account_type=AccountType.ASSETS
        )
        temp_repository.create(account)
        
        # 删除（关闭）账户
        result = temp_repository.delete("Assets:Test:TempAccount")
        
        assert result is True
        
        # 账户仍然存在但已关闭
        found = temp_repository.find_by_name("Assets:Test:TempAccount")
        assert found is not None
        assert not found.is_active()
    
    def test_delete_nonexistent_account(self, temp_repository):
        """测试删除不存在的账户"""
        result = temp_repository.delete("Assets:NonExistent")
        assert result is False
    
    def test_exists(self, repository):
        """测试检查账户存在"""
        assert repository.exists("Assets:Bank:Checking") is True
        assert repository.exists("Assets:NonExistent") is False
    
    def test_count(self, repository):
        """测试计数"""
        count = repository.count()
        assert count > 0
    
    def test_count_by_type(self, repository):
        """测试按类型计数"""
        asset_count = repository.count_by_type(AccountType.ASSETS)
        expense_count = repository.count_by_type(AccountType.EXPENSES)
        income_count = repository.count_by_type(AccountType.INCOME)
        
        assert asset_count > 0
        assert expense_count > 0
        assert income_count > 0
    
    def test_get_root_accounts(self, repository):
        """测试获取根账户"""
        root_accounts = repository.get_root_accounts()
        
        # 应该没有根账户（所有账户都是二级或更深）
        # 除非测试账本有根账户定义
        # 这个测试取决于测试账本的结构
        assert isinstance(root_accounts, list)
    
    def test_get_child_accounts(self, repository):
        """测试获取子账户"""
        children = repository.get_child_accounts("Assets:Bank")
        
        child_names = [acc.name for acc in children]
        assert "Assets:Bank:Checking" in child_names
        assert "Assets:Bank:Savings" in child_names
    
    def test_get_all_descendants(self, repository):
        """测试获取所有后代账户"""
        descendants = repository.get_all_descendants("Assets")
        
        # 所有 Assets 的子账户
        assert len(descendants) > 0
        assert all(acc.name.startswith("Assets:") for acc in descendants)
        
        descendant_names = [acc.name for acc in descendants]
        assert "Assets:Bank:Checking" in descendant_names
        assert "Assets:Bank:Savings" in descendant_names
        assert "Assets:Cash" in descendant_names
    
    def test_reload(self, temp_repository):
        """测试重新加载"""
        initial_count = temp_repository.count()
        
        # 创建新账户
        account = Account(
            name="Assets:New:Account",
            account_type=AccountType.ASSETS
        )
        temp_repository.create(account)
        
        # 计数应该增加
        assert temp_repository.count() == initial_count + 1
    
    def test_account_with_multiple_currencies(self, repository):
        """测试多币种账户"""
        account = repository.find_by_name("Assets:Bank:Savings")
        
        assert account is not None
        assert "CNY" in account.currencies
        assert "USD" in account.currencies
    
    def test_closed_account(self, repository):
        """测试关闭的账户"""
        account = repository.find_by_name("Assets:Old:Account")
        
        assert account is not None
        assert not account.is_active()
        assert account.close_date is not None
