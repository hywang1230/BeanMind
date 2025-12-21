"""账户应用服务单元测试

测试 AccountApplicationService 的所有功能。
"""
import pytest
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository
from backend.application.services import AccountApplicationService


class MockAccountRepository(AccountRepository):
    """账户仓储的 Mock 实现"""
    
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
    
    def get_balance_at_date(self, account_name: str, date: datetime, currency: Optional[str] = None) -> Dict[str, Decimal]:
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
        account = self._accounts[account_name]
        account.close_account(datetime.now())
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
        return [acc for acc in self._accounts.values() if acc.get_parent_account() == parent_name]
    
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


@pytest.fixture
def app_service(mock_repository):
    """创建应用服务实例"""
    return AccountApplicationService(mock_repository)


class TestAccountApplicationService:
    """账户应用服务测试类"""
    
    def test_create_account(self, app_service, mock_repository):
        """测试创建账户"""
        # 先创建父账户
        mock_repository.create(Account(name="Assets", account_type=AccountType.ASSETS))
        
        dto = app_service.create_account(
            name="Assets:Bank",
            account_type="Assets",
            currencies=["CNY", "USD"]
        )
        
        assert dto["name"] == "Assets:Bank"
        assert dto["account_type"] == "Assets"
        assert "CNY" in dto["currencies"]
        assert "USD" in dto["currencies"]
        assert dto["is_active"] is True
    
    def test_create_account_with_date(self, app_service, mock_repository):
        """测试创建账户（指定日期）"""
        mock_repository.create(Account(name="Assets", account_type=AccountType.ASSETS))
        
        date_str = "2025-01-01T00:00:00"
        dto = app_service.create_account(
            name="Assets:Bank",
            account_type="Assets",
            open_date=date_str
        )
        
        assert dto["open_date"] == date_str
    
    def test_get_account(self, app_service, mock_repository):
        """测试获取账户"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        dto = app_service.get_account("Assets:Bank")
        
        assert dto is not None
        assert dto["name"] == "Assets:Bank"
    
    def test_get_account_not_found(self, app_service):
        """测试获取不存在的账户"""
        dto = app_service.get_account("Assets:NonExistent")
        assert dto is None
    
    def test_get_all_accounts(self, app_service, mock_repository):
        """测试获取所有账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        dtos = app_service.get_all_accounts()
        
        assert len(dtos) == 3
    
    def test_get_all_accounts_active_only(self, app_service, mock_repository):
        """测试获取活跃账户"""
        active = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        closed = Account(
            name="Assets:OldBank",
            account_type=AccountType.ASSETS,
            close_date=datetime.now()
        )
        
        mock_repository.create(active)
        mock_repository.create(closed)
        
        dtos = app_service.get_all_accounts(active_only=True)
        
        assert len(dtos) == 1
        assert dtos[0]["name"] == "Assets:Bank"
    
    def test_get_accounts_by_type(self, app_service, mock_repository):
        """测试根据类型获取账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        dtos = app_service.get_accounts_by_type("Assets")
        
        assert len(dtos) == 2
        assert all(dto["account_type"] == "Assets" for dto in dtos)
    
    def test_get_accounts_by_prefix(self, app_service, mock_repository):
        """测试根据前缀获取账户"""
        accounts = [
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Savings", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        dtos = app_service.get_accounts_by_prefix("Assets:Bank")
        
        assert len(dtos) == 2
    
    def test_close_account(self, app_service, mock_repository):
        """测试关闭账户"""
        account = Account(name="Assets:OldBank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        result = app_service.close_account("Assets:OldBank")
        
        assert result is True
        
        # 验证账户已关闭
        dto = app_service.get_account("Assets:OldBank")
        assert dto["is_active"] is False
    
    def test_get_account_balance(self, app_service, mock_repository):
        """测试获取账户余额"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        
        balances = app_service.get_account_balance("Assets:Bank")
        
        assert "CNY" in balances
        assert balances["CNY"] == "1000.00"
    
    def test_get_balances_by_type(self, app_service, mock_repository):
        """测试获取指定类型的余额"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        mock_repository.set_balance("Assets:Cash", "CNY", Decimal("500.00"))
        
        balances = app_service.get_balances_by_type("Assets")
        
        assert "Assets:Bank" in balances
        assert "Assets:Cash" in balances
        assert balances["Assets:Bank"]["CNY"] == "1000.00"
        assert balances["Assets:Cash"]["CNY"] == "500.00"
    
    def test_get_account_summary(self, app_service, mock_repository):
        """测试获取账户摘要"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        summary = app_service.get_account_summary()
        
        assert summary["total_count"] == 3
        assert summary["active_count"] == 3
    
    def test_validate_account_balance(self, app_service, mock_repository):
        """测试验证账户余额"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        
        assert app_service.validate_account_balance("Assets:Bank", "500.00") is True
        assert app_service.validate_account_balance("Assets:Bank", "2000.00") is False
    
    def test_suggest_account_name(self, app_service):
        """测试建议账户名称"""
        suggested = app_service.suggest_account_name("Expenses", "food:dining")
        assert suggested == "Expenses:Food:Dining"
    
    def test_is_valid_account_name(self, app_service):
        """测试验证账户名称"""
        assert app_service.is_valid_account_name("Assets:Bank") is True
        assert app_service.is_valid_account_name("assets:bank") is False
    
    def test_get_child_accounts(self, app_service, mock_repository):
        """测试获取子账户"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Savings", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        children = app_service.get_child_accounts("Assets:Bank")
        
        assert len(children) == 2
        child_names = [c["name"] for c in children]
        assert "Assets:Bank:Checking" in child_names
        assert "Assets:Bank:Savings" in child_names
    
    def test_get_root_accounts(self, app_service, mock_repository):
        """测试获取根账户"""
        accounts = [
            Account(name="Assets", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Expenses", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        roots = app_service.get_root_accounts()
        
        assert len(roots) == 2
        root_names = [r["name"] for r in roots]
        assert "Assets" in root_names
        assert "Expenses" in root_names
    
    def test_dto_conversion(self, app_service, mock_repository):
        """测试 DTO 转换"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            currencies={"CNY", "USD"},
            open_date=datetime(2025, 1, 1)
        )
        mock_repository.create(account)
        
        dto = app_service.get_account("Assets:Bank")
        
        # 验证 DTO 字段
        assert "name" in dto
        assert "account_type" in dto
        assert "currencies" in dto
        assert "is_active" in dto
        assert "open_date" in dto
        assert "close_date" in dto
        assert "depth" in dto
        assert "parent" in dto
        assert "meta" in dto
        
        assert dto["depth"] == 2
        assert dto["parent"] == "Assets"
