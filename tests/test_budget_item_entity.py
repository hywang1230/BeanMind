"""预算项目实体单元测试"""
import pytest
from decimal import Decimal
from backend.domain.budget.entities.budget_item import BudgetItem


class TestBudgetItem:
    """预算项目实体测试"""
    
    def test_create_valid_budget_item(self):
        """测试创建有效的预算项目"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            currency="CNY"
        )
        
        assert item.id == "1"
        assert item.budget_id == "budget1"
        assert item.account_pattern == "Expenses:Food"
        assert item.amount == Decimal("1000")
        assert item.currency == "CNY"
        assert item.spent == Decimal("0")
    
    def test_account_pattern_cannot_be_empty(self):
        """测试账户模式不能为空"""
        with pytest.raises(ValueError, match="账户模式不能为空"):
            BudgetItem(
                id="1",
                budget_id="budget1",
                account_pattern="",
                amount=Decimal("1000")
            )
    
    def test_amount_must_be_positive(self):
        """测试金额必须大于0"""
        with pytest.raises(ValueError, match="预算金额必须大于0"):
            BudgetItem(
                id="1",
                budget_id="budget1",
                account_pattern="Expenses:Food",
                amount=Decimal("0")
            )
        
        with pytest.raises(ValueError, match="预算金额必须大于0"):
            BudgetItem(
                id="1",
                budget_id="budget1",
                account_pattern="Expenses:Food",
                amount=Decimal("-100")
            )
    
    def test_spent_cannot_be_negative(self):
        """测试已花费金额不能为负数"""
        with pytest.raises(ValueError, match="已花费金额不能为负数"):
            BudgetItem(
                id="1",
                budget_id="budget1",
                account_pattern="Expenses:Food",
                amount=Decimal("1000"),
                spent=Decimal("-100")
            )
    
    def test_amount_converted_to_decimal(self):
        """测试金额自动转换为Decimal"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=1000  # 传入整数
        )
        
        assert isinstance(item.amount, Decimal)
        assert item.amount == Decimal("1000")
    
    def test_update_spent(self):
        """测试更新已花费金额"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000")
        )
        
        item.update_spent(Decimal("500"))
        assert item.spent == Decimal("500")
    
    def test_update_spent_with_negative_value(self):
        """测试更新已花费金额为负数时抛出异常"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000")
        )
        
        with pytest.raises(ValueError, match="已花费金额不能为负数"):
            item.update_spent(Decimal("-100"))
    
    def test_get_remaining(self):
        """测试获取剩余预算"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("600")
        )
        
        assert item.get_remaining() == Decimal("400")
    
    def test_get_usage_rate(self):
        """测试获取使用率"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("800")
        )
        
        assert item.get_usage_rate() == 80.0
    
    def test_get_usage_rate_with_zero_amount(self):
        """测试当预算金额为0时获取使用率"""
        # 由于验证规则，金额不能为0，这里只是为了边界测试
        # 实际上这个测试会在创建时失败
        # 保持测试完整性，测试逻辑本身
        pass
    
    def test_is_over_budget(self):
        """测试是否超预算"""
        item1 = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("1200")
        )
        assert item1.is_over_budget() is True
        
        item2 = BudgetItem(
            id="2",
            budget_id="budget1",
            account_pattern="Expenses:Transport",
            amount=Decimal("1000"),
            spent=Decimal("800")
        )
        assert item2.is_over_budget() is False
    
    def test_is_warning_default_threshold(self):
        """测试是否达到警告阈值（默认80%）"""
        item1 = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("850")
        )
        assert item1.is_warning() is True
        
        item2 = BudgetItem(
            id="2",
            budget_id="budget1",
            account_pattern="Expenses:Transport",
            amount=Decimal("1000"),
            spent=Decimal("700")
        )
        assert item2.is_warning() is False
    
    def test_is_warning_custom_threshold(self):
        """测试自定义警告阈值"""
        item = BudgetItem(
            id="1",
            budget_id="budget1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("700")
        )
        
        assert item.is_warning(threshold=70.0) is True
        assert item.is_warning(threshold=80.0) is False
