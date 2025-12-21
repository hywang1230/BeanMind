"""账户仓储接口单元测试

测试 AccountRepository 接口的所有方法定义及 Mock 实现。
"""
import pytest
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository


class MockAccountRepository(AccountRepository):
    """账户仓储的 Mock 实现，用于测试"""
    
    def __init__(self):
        self._accounts: Dict[str, Account] = {}
        self._balances: Dict[str, Dict[str, Decimal]] = {}
    
    def find_by_name(self, name: str) -> Optional[Account]:
        return self._accounts.get(name)
    
    def find_all(self) -> List[Account]:
        return list(self._accounts.values())
    
    def find_by_type(self, account_type: AccountType) -> List[Account]:
        return [acc for acc in self._accounts.values() if acc.account_type == account_type]
    
    def find_by_prefix(self, prefix: str) -> List[Account]:
        return [acc for acc in self._accounts.values() if acc.name.startswith(prefix)]
    
    def find_active_accounts(self) -> List[Account]:
        return [acc for acc in self._accounts.values() if acc.is_active()]
    
    def get_balance(self, account_name: str, currency: Optional[str] = None) -> Dict[str, Decimal]:
        balances = self._balances.get(account_name, {})
        if currency:
            return {currency: balances.get(currency, Decimal("0"))}
        return balances.copy()
    
    def get_balances_by_type(self, account_type: AccountType, currency: Optional[str] = None) -> Dict[str, Dict[str, Decimal]]:
        result = {}
        accounts = self.find_by_type(account_type)
        for acc in accounts:
            result[acc.name] = self.get_balance(acc.name, currency)
        return result
    
    def get_balance_at_date(
        self, 
        account_name: str, 
        date: datetime, 
        currency: Optional[str] = None
    ) -> Dict[str, Decimal]:
        # Mock 实现：简单返回当前余额
        return self.get_balance(account_name, currency)
    
    def create(self, account: Account) -> Account:
        if account.name in self._accounts:
            raise ValueError(f"账户 '{account.name}' 已存在")
        self._accounts[account.name] = account
        self._balances[account.name] = {}
        return account
    
    def update(self, account: Account) -> Account:
        if account.name not in self._accounts:
            raise ValueError(f"账户 '{account.name}' 不存在")
        self._accounts[account.name] = account
        return account
    
    def delete(self, account_name: str) -> bool:
        if account_name not in self._accounts:
            return False
        del self._accounts[account_name]
        if account_name in self._balances:
            del self._balances[account_name]
        return True
    
    def exists(self, account_name: str) -> bool:
        return account_name in self._accounts
    
    def count(self) -> int:
        return len(self._accounts)
    
    def count_by_type(self, account_type: AccountType) -> int:
        return len(self.find_by_type(account_type))
    
    def get_root_accounts(self) -> List[Account]:
        return [acc for acc in self._accounts.values() if acc.get_depth() == 1]
    
    def get_child_accounts(self, parent_name: str) -> List[Account]:
        return [
            acc for acc in self._accounts.values()
            if acc.get_parent_account() == parent_name
        ]
    
    def get_all_descendants(self, parent_name: str) -> List[Account]:
        descendants = []
        for acc in self._accounts.values():
            if acc.name.startswith(parent_name + ":"):
                descendants.append(acc)
        return descendants
    
    def set_balance(self, account_name: str, currency: str, amount: Decimal):
        """测试辅助方法：设置账户余额"""
        if account_name not in self._balances:
            self._balances[account_name] = {}
        self._balances[account_name][currency] = amount


@pytest.fixture
def mock_repository():
    """创建 Mock 仓储"""
    return MockAccountRepository()


class TestAccountRepository:
    """账户仓储接口测试类"""
    
    def test_create_account(self, mock_repository):
        """测试创建账户"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        
        created = mock_repository.create(account)
        
        assert created.name == "Assets:Bank"
        assert mock_repository.exists("Assets:Bank")
    
    def test_create_duplicate_account(self, mock_repository):
        """测试创建重复账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        with pytest.raises(ValueError, match="已存在"):
            mock_repository.create(account)
    
    def test_find_by_name(self, mock_repository):
        """测试根据名称查找账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        found = mock_repository.find_by_name("Assets:Bank")
        
        assert found is not None
        assert found.name == "Assets:Bank"
    
    def test_find_by_name_not_found(self, mock_repository):
        """测试查找不存在的账户"""
        found = mock_repository.find_by_name("Assets:NonExistent")
        assert found is None
    
    def test_find_all(self, mock_repository):
        """测试获取所有账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES),
            Account(name="Income:Salary", account_type=AccountType.INCOME)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        all_accounts = mock_repository.find_all()
        
        assert len(all_accounts) == 3
    
    def test_find_by_type(self, mock_repository):
        """测试根据类型查找账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        asset_accounts = mock_repository.find_by_type(AccountType.ASSETS)
        
        assert len(asset_accounts) == 2
        assert all(acc.account_type == AccountType.ASSETS for acc in asset_accounts)
    
    def test_find_by_prefix(self, mock_repository):
        """测试根据前缀查找账户"""
        accounts = [
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Savings", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        bank_accounts = mock_repository.find_by_prefix("Assets:Bank")
        
        assert len(bank_accounts) == 2
        assert all(acc.name.startswith("Assets:Bank") for acc in bank_accounts)
    
    def test_find_active_accounts(self, mock_repository):
        """测试获取活跃账户"""
        active = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        closed = Account(
            name="Assets:OldBank",
            account_type=AccountType.ASSETS,
            close_date=datetime.now()
        )
        
        mock_repository.create(active)
        mock_repository.create(closed)
        
        active_accounts = mock_repository.find_active_accounts()
        
        assert len(active_accounts) == 1
        assert active_accounts[0].name == "Assets:Bank"
    
    def test_get_balance(self, mock_repository):
        """测试获取账户余额"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        # 设置余额
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        mock_repository.set_balance("Assets:Bank", "USD", Decimal("100.00"))
        
        # 获取所有货币余额
        balances = mock_repository.get_balance("Assets:Bank")
        assert balances["CNY"] == Decimal("1000.00")
        assert balances["USD"] == Decimal("100.00")
        
        # 获取指定货币余额
        cny_balance = mock_repository.get_balance("Assets:Bank", "CNY")
        assert cny_balance["CNY"] == Decimal("1000.00")
    
    def test_get_balances_by_type(self, mock_repository):
        """测试获取指定类型所有账户的余额"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        mock_repository.set_balance("Assets:Cash", "CNY", Decimal("500.00"))
        
        balances = mock_repository.get_balances_by_type(AccountType.ASSETS)
        
        assert "Assets:Bank" in balances
        assert "Assets:Cash" in balances
        assert balances["Assets:Bank"]["CNY"] == Decimal("1000.00")
        assert balances["Assets:Cash"]["CNY"] == Decimal("500.00")
    
    def test_get_balance_at_date(self, mock_repository):
        """测试获取指定日期的余额"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        
        date = datetime(2025, 1, 1)
        balances = mock_repository.get_balance_at_date("Assets:Bank", date)
        
        assert "CNY" in balances
    
    def test_update_account(self, mock_repository):
        """测试更新账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        # 更新账户
        account.add_currency("CNY")
        updated = mock_repository.update(account)
        
        assert "CNY" in updated.currencies
    
    def test_update_nonexistent_account(self, mock_repository):
        """测试更新不存在的账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        
        with pytest.raises(ValueError, match="不存在"):
            mock_repository.update(account)
    
    def test_delete_account(self, mock_repository):
        """测试删除账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        result = mock_repository.delete("Assets:Bank")
        
        assert result is True
        assert not mock_repository.exists("Assets:Bank")
    
    def test_delete_nonexistent_account(self, mock_repository):
        """测试删除不存在的账户"""
        result = mock_repository.delete("Assets:NonExistent")
        assert result is False
    
    def test_exists(self, mock_repository):
        """测试检查账户存在"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        assert mock_repository.exists("Assets:Bank") is True
        assert mock_repository.exists("Assets:NonExistent") is False
    
    def test_count(self, mock_repository):
        """测试计数"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES),
            Account(name="Income:Salary", account_type=AccountType.INCOME)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        assert mock_repository.count() == 3
    
    def test_count_by_type(self, mock_repository):
        """测试按类型计数"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        assert mock_repository.count_by_type(AccountType.ASSETS) == 2
        assert mock_repository.count_by_type(AccountType.EXPENSES) == 1
        assert mock_repository.count_by_type(AccountType.INCOME) == 0
    
    def test_get_root_accounts(self, mock_repository):
        """测试获取根账户"""
        accounts = [
            Account(name="Assets", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Expenses", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        root_accounts = mock_repository.get_root_accounts()
        
        assert len(root_accounts) == 2
        assert all(acc.get_depth() == 1 for acc in root_accounts)
    
    def test_get_child_accounts(self, mock_repository):
        """测试获取子账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Savings", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        children = mock_repository.get_child_accounts("Assets:Bank")
        
        assert len(children) == 2
        assert all(acc.get_parent_account() == "Assets:Bank" for acc in children)
    
    def test_get_all_descendants(self, mock_repository):
        """测试获取所有后代账户"""
        accounts = [
            Account(name="Assets", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        descendants = mock_repository.get_all_descendants("Assets")
        
        assert len(descendants) == 3
        assert all(acc.name.startswith("Assets:") for acc in descendants)
    
    def test_repository_interface_methods(self, mock_repository):
        """测试仓储接口方法完整性"""
        # 确保所有抽象方法都有实现
        assert hasattr(mock_repository, 'find_by_name')
        assert hasattr(mock_repository, 'find_all')
        assert hasattr(mock_repository, 'find_by_type')
        assert hasattr(mock_repository, 'find_by_prefix')
        assert hasattr(mock_repository, 'find_active_accounts')
        assert hasattr(mock_repository, 'get_balance')
        assert hasattr(mock_repository, 'get_balances_by_type')
        assert hasattr(mock_repository, 'get_balance_at_date')
        assert hasattr(mock_repository, 'create')
        assert hasattr(mock_repository, 'update')
        assert hasattr(mock_repository, 'delete')
        assert hasattr(mock_repository, 'exists')
        assert hasattr(mock_repository, 'count')
        assert hasattr(mock_repository, 'count_by_type')
        assert hasattr(mock_repository, 'get_root_accounts')
        assert hasattr(mock_repository, 'get_child_accounts')
        assert hasattr(mock_repository, 'get_all_descendants')
