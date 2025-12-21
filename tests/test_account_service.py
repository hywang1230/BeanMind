"""账户领域服务单元测试

测试 AccountService 的所有业务逻辑和验证规则。
"""
import pytest
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime

from backend.domain.account.entities import Account, AccountType
from backend.domain.account.repositories import AccountRepository
from backend.domain.account.services import AccountService


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
        # 模拟关闭账户
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
def account_service(mock_repository):
    """创建账户服务实例"""
    return AccountService(mock_repository)


class TestAccountService:
    """账户服务测试类"""
    
    def test_create_account_success(self, account_service, mock_repository):
        """测试创建账户成功"""
        # 先创建父账户
        mock_repository.create(Account(name="Assets", account_type=AccountType.ASSETS))
        
        account = account_service.create_account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            currencies=["CNY"]
        )
        
        assert account.name == "Assets:Bank"
        assert account.account_type == AccountType.ASSETS
        assert "CNY" in account.currencies
    
    def test_create_account_invalid_name_empty(self, account_service):
        """测试创建账户失败（空名称）"""
        with pytest.raises(ValueError, match="账户名称不能为空"):
            account_service.create_account("", AccountType.ASSETS)
    
    def test_create_account_invalid_name_lowercase(self, account_service):
        """测试创建账户失败（小写字母开头）"""
        with pytest.raises(ValueError, match="必须以大写字母开头"):
            account_service.create_account("assets:Bank", AccountType.ASSETS)
    
    def test_create_account_invalid_name_special_chars(self, account_service):
        """测试创建账户失败（包含特殊字符）"""
        with pytest.raises(ValueError, match="包含无效字符"):
            account_service.create_account("Assets:Bank@", AccountType.ASSETS)
    
    def test_create_account_type_mismatch(self, account_service, mock_repository):
        """测试创建账户失败（类型不匹配）"""
        with pytest.raises(ValueError, match="不匹配"):
            account_service.create_account("Assets:Bank", AccountType.INCOME)
    
    def test_create_account_already_exists(self, account_service, mock_repository):
        """测试创建账户失败（账户已存在）"""
        mock_repository.create(Account(name="Assets", account_type=AccountType.ASSETS))
        mock_repository.create(Account(name="Assets:Bank", account_type=AccountType.ASSETS))
        
        with pytest.raises(ValueError, match="已存在"):
            account_service.create_account("Assets:Bank", AccountType.ASSETS)
    
    def test_create_account_parent_not_exists(self, account_service):
        """测试创建账户失败（父账户不存在）"""
        with pytest.raises(ValueError, match="父账户.*不存在"):
            account_service.create_account("Assets:Bank:Checking", AccountType.ASSETS)
    
    def test_close_account_success(self, account_service, mock_repository):
        """测试关闭账户成功"""
        account = Account(name="Assets:OldBank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        
        result = account_service.close_account("Assets:OldBank")
        
        assert result is True
        # 验证账户已关闭
        closed_account = mock_repository.find_by_name("Assets:OldBank")
        assert not closed_account.is_active()
    
    def test_close_account_not_exists(self, account_service):
        """测试关闭账户失败（账户不存在）"""
        with pytest.raises(ValueError, match="不存在"):
            account_service.close_account("Assets:NonExistent")
    
    def test_close_account_already_closed(self, account_service, mock_repository):
        """测试关闭账户失败（账户已关闭）"""
        account = Account(
            name="Assets:ClosedBank",
            account_type=AccountType.ASSETS,
            close_date=datetime.now()
        )
        mock_repository.create(account)
        
        with pytest.raises(ValueError, match="已经关闭"):
            account_service.close_account("Assets:ClosedBank")
    
    def test_close_account_with_active_children(self, account_service, mock_repository):
        """测试关闭账户失败（有活跃的子账户）"""
        parent = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        child = Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS)
        
        mock_repository.create(parent)
        mock_repository.create(child)
        
        with pytest.raises(ValueError, match="有活跃的子账户"):
            account_service.close_account("Assets:Bank")
    
    def test_get_account_hierarchy(self, account_service, mock_repository):
        """测试获取账户层级"""
        accounts = [
            Account(name="Assets", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        hierarchy = account_service.get_account_hierarchy("Assets")
        
        assert "Assets" in hierarchy
        assert "_children" in hierarchy["Assets"]
        assert "Bank" in hierarchy["Assets"]["_children"]
    
    def test_validate_account_balance(self, account_service, mock_repository):
        """测试验证账户余额"""
        account = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        mock_repository.create(account)
        mock_repository.set_balance("Assets:Bank", "CNY", Decimal("1000.00"))
        
        # 余额充足
        assert account_service.validate_account_balance("Assets:Bank", Decimal("500.00")) is True
        
        # 余额不足
        assert account_service.validate_account_balance("Assets:Bank", Decimal("2000.00")) is False
    
    def test_get_account_summary(self, account_service, mock_repository):
        """测试获取账户摘要"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES),
            Account(name="Assets:OldBank", account_type=AccountType.ASSETS, close_date=datetime.now())
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        summary = account_service.get_account_summary()
        
        assert summary["total_count"] == 4
        assert summary["active_count"] == 3
        assert summary["closed_count"] == 1
        assert "by_type" in summary
    
    def test_get_account_summary_by_type(self, account_service, mock_repository):
        """测试获取指定类型的账户摘要"""
        accounts = [
            Account(name="Assets:Bank", account_type=AccountType.ASSETS),
            Account(name="Assets:Cash", account_type=AccountType.ASSETS),
            Account(name="Expenses:Food", account_type=AccountType.EXPENSES)
        ]
        
        for acc in accounts:
            mock_repository.create(acc)
        
        summary = account_service.get_account_summary(AccountType.ASSETS)
        
        assert summary["total_count"] == 2
    
    def test_suggest_account_name(self, account_service):
        """测试建议账户名称"""
        suggested = account_service.suggest_account_name(AccountType.EXPENSES, "food:dining")
        
        assert suggested == "Expenses:Food:Dining"
    
    def test_is_valid_account_name(self, account_service):
        """测试检查账户名称有效性"""
        assert account_service.is_valid_account_name("Assets:Bank") is True
        assert account_service.is_valid_account_name("assets:bank") is False
        assert account_service.is_valid_account_name("") is False
        assert account_service.is_valid_account_name("Assets:Bank@") is False
    
    def test_create_root_account(self, account_service):
        """测试创建根账户"""
        account = account_service.create_account("Assets", AccountType.ASSETS)
        
        assert account.name == "Assets"
        assert account.get_depth() == 1
    
    def test_create_nested_account(self, account_service, mock_repository):
        """测试创建嵌套账户"""
        # 创建层级账户
        mock_repository.create(Account(name="Assets", account_type=AccountType.ASSETS))
        mock_repository.create(Account(name="Assets:Bank", account_type=AccountType.ASSETS))
        
        account = account_service.create_account(
            "Assets:Bank:Checking",
            AccountType.ASSETS
        )
        
        assert account.name == "Assets:Bank:Checking"
        assert account.get_depth() == 3
    
    def test_all_account_types(self, account_service, mock_repository):
        """测试所有账户类型"""
        account_types = [
            (AccountType.ASSETS, "Assets:Test"),
            (AccountType.LIABILITIES, "Liabilities:Test"),
            (AccountType.EQUITY, "Equity:Test"),
            (AccountType.INCOME, "Income:Test"),
            (AccountType.EXPENSES, "Expenses:Test")
        ]
        
        for acc_type, name in account_types:
            # 创建根账户
            root_name = name.split(":")[0]
            if not mock_repository.exists(root_name):
                mock_repository.create(Account(name=root_name, account_type=acc_type))
            
            account = account_service.create_account(name, acc_type)
            assert account.account_type == acc_type
