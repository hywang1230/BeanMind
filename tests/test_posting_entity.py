"""Posting 领域实体单元测试

测试 Posting 实体的所有功能。
"""
import pytest
from decimal import Decimal

from backend.domain.transaction.entities import Posting


class TestPosting:
    """Posting 实体测试类"""
    
    def test_create_posting_minimal(self):
        """测试创建 Posting（最小数据）"""
        posting = Posting(
            account="Assets:Bank:Checking",
            amount=Decimal("100.50"),
            currency="CNY"
        )
        
        assert posting.account == "Assets:Bank:Checking"
        assert posting.amount == Decimal("100.50")
        assert posting.currency == "CNY"
        assert posting.cost is None
        assert posting.price is None
        assert posting.flag is None
        assert posting.meta == {}
    
    def test_create_posting_with_cost(self):
        """测试创建带成本的 Posting"""
        posting = Posting(
            account="Assets:Stocks:AAPL",
            amount=Decimal("10"),
            currency="AAPL",
            cost=Decimal("150.00"),
            cost_currency="USD"
        )
        
        assert posting.has_cost() is True
        assert posting.cost == Decimal("150.00")
        assert posting.cost_currency == "USD"
        assert posting.get_total_cost() == Decimal("1500.00")
    
    def test_create_posting_with_price(self):
        """测试创建带市场价格的 Posting"""
        posting = Posting(
            account="Assets:Stocks:AAPL",
            amount=Decimal("10"),
            currency="AAPL",
            price=Decimal("155.00"),
            price_currency="USD"
        )
        
        assert posting.has_price() is True
        assert posting.price == Decimal("155.00")
        assert posting.price_currency == "USD"
        assert posting.get_total_value() == Decimal("1550.00")
    
    def test_account_validation_empty(self):
        """测试账户名称验证（空名称）"""
        with pytest.raises(ValueError, match="账户名称不能为空"):
            Posting(account="", amount=Decimal("100"), currency="CNY")
    
    def test_currency_validation_empty(self):
        """测试货币代码验证（空代码）"""
        with pytest.raises(ValueError, match="货币代码不能为空"):
            Posting(account="Assets:Bank", amount=Decimal("100"), currency="")
    
    def test_currency_validation_invalid_length(self):
        """测试货币代码验证（长度不对）"""
        with pytest.raises(ValueError, match="无效的货币代码"):
            Posting(account="Assets:Bank", amount=Decimal("100"), currency="U")  # 太短（1字符）
    
    def test_currency_normalization(self):
        """测试货币代码自动转大写"""
        posting = Posting(
            account="Assets:Bank",
            amount=Decimal("100"),
            currency="cny"
        )
        assert posting.currency == "CNY"
    
    def test_amount_conversion(self):
        """测试金额自动转换为 Decimal"""
        posting = Posting(
            account="Assets:Bank",
            amount=100.50,
            currency="CNY"
        )
        assert isinstance(posting.amount, Decimal)
        assert posting.amount == Decimal("100.50")
    
    def test_cost_validation_incomplete(self):
        """测试成本验证（成本和货币必须同时存在）"""
        with pytest.raises(ValueError, match="成本价格和成本货币必须同时指定"):
            Posting(
                account="Assets:Stocks",
                amount=Decimal("10"),
                currency="AAPL",
                cost=Decimal("150")
            )
    
    def test_price_validation_incomplete(self):
        """测试价格验证（价格和货币必须同时存在）"""
        with pytest.raises(ValueError, match="市场价格和价格货币必须同时指定"):
            Posting(
                account="Assets:Stocks",
                amount=Decimal("10"),
                currency="AAPL",
                price_currency="USD"
            )
    
    def test_flag_validation_invalid(self):
        """测试标记验证（无效的标记）"""
        with pytest.raises(ValueError, match="无效的标记"):
            Posting(
                account="Assets:Bank",
                amount=Decimal("100"),
                currency="CNY",
                flag="X"
            )
    
    def test_flag_valid(self):
        """测试有效的标记"""
        cleared = Posting(
            account="Assets:Bank",
            amount=Decimal("100"),
            currency="CNY",
            flag="*"
        )
        assert cleared.flag == "*"
        
        pending = Posting(
            account="Assets:Bank",
            amount=Decimal("100"),
            currency="CNY",
            flag="!"
        )
        assert pending.flag == "!"
    
    def test_is_debit(self):
        """测试判断是否为借记"""
        debit = Posting(
            account="Assets:Bank",
            amount=Decimal("100"),
            currency="CNY"
        )
        assert debit.is_debit() is True
        assert debit.is_credit() is False
    
    def test_is_credit(self):
        """测试判断是否为贷记"""
        credit = Posting(
            account="Expenses:Food",
            amount=Decimal("-100"),
            currency="CNY"
        )
        assert credit.is_credit() is True
        assert credit.is_debit() is False
    
    def test_get_absolute_amount(self):
        """测试获取金额绝对值"""
        posting = Posting(
            account="Assets:Bank",
            amount=Decimal("-100.50"),
            currency="CNY"
        )
        assert posting.get_absolute_amount() == Decimal("100.50")
    
    def test_to_dict_minimal(self):
        """测试转换为字典（最小数据）"""
        posting = Posting(
            account="Assets:Bank",
            amount=Decimal("100.50"),
            currency="CNY"
        )
        
        data = posting.to_dict()
        
        assert data["account"] == "Assets:Bank"
        assert data["amount"] == "100.50"
        assert data["currency"] == "CNY"
        assert "cost" not in data
        assert "price" not in data
        assert "flag" not in data
    
    def test_to_dict_full(self):
        """测试转换为字典（完整数据）"""
        posting = Posting(
            account="Assets:Stocks:AAPL",
            amount=Decimal("10"),
            currency="AAPL",
            cost=Decimal("150.00"),
            cost_currency="USD",
            price=Decimal("155.00"),
            price_currency="USD",
            flag="*",
            meta={"note": "test"}
        )
        
        data = posting.to_dict()
        
        assert data["account"] == "Assets:Stocks:AAPL"
        assert data["amount"] == "10"
        assert data["currency"] == "AAPL"
        assert data["cost"] == "150.00"
        assert data["cost_currency"] == "USD"
        assert data["price"] == "155.00"
        assert data["price_currency"] == "USD"
        assert data["flag"] == "*"
        assert data["meta"] == {"note": "test"}
    
    def test_from_dict_minimal(self):
        """测试从字典创建（最小数据）"""
        data = {
            "account": "Assets:Bank",
            "amount": "100.50",
            "currency": "CNY"
        }
        
        posting = Posting.from_dict(data)
        
        assert posting.account == "Assets:Bank"
        assert posting.amount == Decimal("100.50")
        assert posting.currency == "CNY"
    
    def test_from_dict_full(self):
        """测试从字典创建（完整数据）"""
        data = {
            "account": "Assets:Stocks:AAPL",
            "amount": "10",
            "currency": "AAPL",
            "cost": "150.00",
            "cost_currency": "USD",
            "price": "155.00",
            "price_currency": "USD",
            "flag": "*",
            "meta": {"note": "test"}
        }
        
        posting = Posting.from_dict(data)
        
        assert posting.account == "Assets:Stocks:AAPL"
        assert posting.amount == Decimal("10")
        assert posting.cost == Decimal("150.00")
        assert posting.price == Decimal("155.00")
        assert posting.flag == "*"
        assert posting.meta == {"note": "test"}
    
    def test_repr(self):
        """测试字符串表示"""
        posting = Posting(
            account="Assets:Bank",
            amount=Decimal("1000.50"),
            currency="CNY"
        )
        
        repr_str = repr(posting)
        assert "Assets:Bank" in repr_str
        assert "1,000.50 CNY" in repr_str
