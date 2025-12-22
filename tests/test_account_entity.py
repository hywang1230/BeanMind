"""账户领域实体单元测试

测试 Account 实体和 AccountType 枚举的所有功能。
"""
import pytest
from datetime import datetime

from backend.domain.account.entities import Account, AccountType


class TestAccountType:
    """账户类型枚举测试类"""
    
    def test_account_types(self):
        """测试所有账户类型"""
        assert AccountType.ASSETS.value == "Assets"
        assert AccountType.LIABILITIES.value == "Liabilities"
        assert AccountType.EQUITY.value == "Equity"
        assert AccountType.INCOME.value == "Income"
        assert AccountType.EXPENSES.value == "Expenses"
    
    def test_from_string_valid(self):
        """测试从字符串转换（有效值）"""
        assert AccountType.from_string("Assets") == AccountType.ASSETS
        assert AccountType.from_string("Liabilities") == AccountType.LIABILITIES
        assert AccountType.from_string("Equity") == AccountType.EQUITY
        assert AccountType.from_string("Income") == AccountType.INCOME
        assert AccountType.from_string("Expenses") == AccountType.EXPENSES
    
    def test_from_string_invalid(self):
        """测试从字符串转换（无效值）"""
        with pytest.raises(ValueError, match="无效的账户类型"):
            AccountType.from_string("Invalid")
    
    def test_is_balance_sheet_account(self):
        """测试是否为资产负债表账户"""
        assert AccountType.ASSETS.is_balance_sheet_account() is True
        assert AccountType.LIABILITIES.is_balance_sheet_account() is True
        assert AccountType.EQUITY.is_balance_sheet_account() is True
        assert AccountType.INCOME.is_balance_sheet_account() is False
        assert AccountType.EXPENSES.is_balance_sheet_account() is False
    
    def test_is_income_statement_account(self):
        """测试是否为损益表账户"""
        assert AccountType.INCOME.is_income_statement_account() is True
        assert AccountType.EXPENSES.is_income_statement_account() is True
        assert AccountType.ASSETS.is_income_statement_account() is False
        assert AccountType.LIABILITIES.is_income_statement_account() is False
        assert AccountType.EQUITY.is_income_statement_account() is False


class TestAccount:
    """账户实体测试类"""
    
    def test_create_account_minimal(self):
        """测试创建账户（最小数据）"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        
        assert account.name == "Assets:Bank"
        assert account.account_type == AccountType.ASSETS
        assert len(account.currencies) == 0
        assert account.meta == {}
        assert account.open_date is None
        assert account.close_date is None
    
    def test_create_account_full(self):
        """测试创建账户（完整数据）"""
        now = datetime.now()
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS,
            currencies={"CNY", "USD"},
            meta={"institution": "Bank of China"},
            open_date=now,
            created_at=now,
            updated_at=now
        )
        
        assert account.name == "Assets:Bank:Checking"
        assert account.account_type == AccountType.ASSETS
        assert "CNY" in account.currencies
        assert "USD" in account.currencies
        assert account.meta["institution"] == "Bank of China"
        assert account.open_date == now
    
    def test_account_name_validation_empty(self):
        """测试账户名称验证（空名称）"""
        with pytest.raises(ValueError, match="账户名称不能为空"):
            Account(name="", account_type=AccountType.ASSETS)
    
    def test_account_name_validation_invalid_format(self):
        """测试账户名称验证（无效格式）"""
        # 小写字母开头
        with pytest.raises(ValueError, match="无效的账户名称格式"):
            Account(name="assets:Bank", account_type=AccountType.ASSETS)
    
    def test_account_type_mismatch(self):
        """测试账户类型与名称不匹配"""
        with pytest.raises(ValueError, match="账户名称.*与账户类型.*不匹配"):
            Account(name="Assets:Bank", account_type=AccountType.INCOME)
    
    def test_close_date_before_open_date(self):
        """测试关闭日期早于开户日期"""
        open_date = datetime(2025, 1, 1)
        close_date = datetime(2024, 12, 31)
        
        with pytest.raises(ValueError, match="账户关闭日期不能早于开户日期"):
            Account(
                name="Assets:Bank",
                account_type=AccountType.ASSETS,
                open_date=open_date,
                close_date=close_date
            )
    
    def test_is_active(self):
        """测试账户是否活跃"""
        active_account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        assert active_account.is_active() is True
        
        closed_account = Account(
            name="Assets:OldBank",
            account_type=AccountType.ASSETS,
            close_date=datetime.now()
        )
        assert closed_account.is_active() is False
    
    def test_get_root_account(self):
        """测试获取根账户"""
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS
        )
        assert account.get_root_account() == "Assets"
    
    def test_get_account_levels(self):
        """测试获取账户层级"""
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS
        )
        levels = account.get_account_levels()
        assert levels == ["Assets", "Bank", "Checking"]
    
    def test_get_parent_account(self):
        """测试获取父账户"""
        # 有父账户（三层）
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS
        )
        assert account.get_parent_account() == "Assets:Bank"
        
        # 两层账户的父账户是根账户
        level2_account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        assert level2_account.get_parent_account() == "Assets"
    
    def test_get_depth(self):
        """测试获取账户深度"""
        level2 = Account(name="Assets:Bank", account_type=AccountType.ASSETS)
        assert level2.get_depth() == 2
        
        level3 = Account(name="Assets:Bank:Checking", account_type=AccountType.ASSETS)
        assert level3.get_depth() == 3
        
        level4 = Account(name="Assets:Bank:Checking:Main", account_type=AccountType.ASSETS)
        assert level4.get_depth() == 4
    
    def test_add_currency(self):
        """测试添加货币"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        
        account.add_currency("CNY")
        assert "CNY" in account.currencies
        
        account.add_currency("usd")  # 应自动转换为大写
        assert "USD" in account.currencies
    
    def test_add_currency_invalid(self):
        """测试添加无效货币"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS
        )
        
        # 空货币代码
        with pytest.raises(ValueError, match="货币代码不能为空"):
            account.add_currency("")
        
        # 长度不对
        with pytest.raises(ValueError, match="无效的货币代码"):
            account.add_currency("US")
    
    def test_supports_currency(self):
        """测试是否支持货币"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            currencies={"CNY", "USD"}
        )
        
        assert account.supports_currency("CNY") is True
        assert account.supports_currency("usd") is True  # 大小写不敏感
        assert account.supports_currency("EUR") is False
    
    def test_close_account(self):
        """测试关闭账户"""
        open_date = datetime(2025, 1, 1)
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            open_date=open_date
        )
        
        close_date = datetime(2025, 12, 31)
        account.close_account(close_date)
        
        assert account.close_date == close_date
        assert account.is_active() is False
    
    def test_close_account_before_open(self):
        """测试关闭日期早于开户日期"""
        open_date = datetime(2025, 1, 1)
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            open_date=open_date
        )
        
        close_date = datetime(2024, 12, 31)
        with pytest.raises(ValueError, match="账户关闭日期不能早于开户日期"):
            account.close_account(close_date)
    
    def test_to_dict(self):
        """测试转换为字典"""
        now = datetime(2025, 1, 1, 12, 0, 0)
        account = Account(
            name="Assets:Bank:Checking",
            account_type=AccountType.ASSETS,
            currencies={"CNY", "USD"},
            meta={"note": "test"},
            open_date=now,
            created_at=now
        )
        
        data = account.to_dict()
        
        assert data["name"] == "Assets:Bank:Checking"
        assert data["account_type"] == "Assets"
        assert set(data["currencies"]) == {"CNY", "USD"}
        assert data["meta"] == {"note": "test"}
        assert data["open_date"] == now.isoformat()
    
    def test_from_dict(self):
        """测试从字典创建"""
        now = datetime(2025, 1, 1, 12, 0, 0)
        data = {
            "name": "Assets:Bank:Checking",
            "account_type": "Assets",
            "currencies": ["CNY", "USD"],
            "meta": {"note": "test"},
            "open_date": now.isoformat(),
            "close_date": None,
            "created_at": now.isoformat(),
            "updated_at": None
        }
        
        account = Account.from_dict(data)
        
        assert account.name == "Assets:Bank:Checking"
        assert account.account_type == AccountType.ASSETS
        assert "CNY" in account.currencies
        assert "USD" in account.currencies
        assert account.meta == {"note": "test"}
        assert account.open_date == now
    
    def test_repr(self):
        """测试字符串表示"""
        account = Account(
            name="Assets:Bank",
            account_type=AccountType.ASSETS,
            currencies={"CNY"}
        )
        
        repr_str = repr(account)
        assert "Assets:Bank" in repr_str
        assert "Assets" in repr_str
        assert "CNY" in repr_str
        assert "active" in repr_str
    
    def test_all_account_types(self):
        """测试所有账户类型"""
        types_and_names = [
            (AccountType.ASSETS, "Assets:Bank"),
            (AccountType.LIABILITIES, "Liabilities:CreditCard"),
            (AccountType.EQUITY, "Equity:OpeningBalances"),
            (AccountType.INCOME, "Income:Salary"),
            (AccountType.EXPENSES, "Expenses:Food"),
        ]
        
        for account_type, name in types_and_names:
            account = Account(name=name, account_type=account_type)
            assert account.account_type == account_type
            assert account.name == name
