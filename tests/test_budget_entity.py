"""预算实体单元测试"""
import pytest
from datetime import date
from decimal import Decimal
from backend.domain.budget.entities.budget import Budget, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem


class TestBudget:
    """预算实体测试"""
    
    def test_create_valid_budget(self):
        """测试创建有效的预算"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="月度预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            is_active=True
        )
        
        assert budget.id == "1"
        assert budget.name == "月度预算"
        assert budget.period_type == PeriodType.MONTHLY
        assert budget.is_active is True
    
    def test_budget_name_cannot_be_empty(self):
        """测试预算名称不能为空"""
        with pytest.raises(ValueError, match="预算名称不能为空"):
            Budget(
                id="1",
                user_id="user1",
                name="",
                period_type=PeriodType.MONTHLY,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31)
            )
    
    def test_end_date_cannot_before_start_date(self):
        """测试结束日期不能早于开始日期"""
        with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
            Budget(
                id="1",
                user_id="user1",
                name="预算",
                period_type=PeriodType.MONTHLY,
                start_date=date(2025, 1, 31),
                end_date=date(2025, 1, 1)
            )
    
    def test_custom_period_must_have_end_date(self):
        """测试自定义周期必须设置结束日期"""
        with pytest.raises(ValueError, match="自定义周期必须设置结束日期"):
            Budget(
                id="1",
                user_id="user1",
                name="自定义预算",
                period_type=PeriodType.CUSTOM,
                start_date=date(2025, 1, 1),
                end_date=None
            )
    
    def test_deactivate_budget(self):
        """测试停用预算"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            is_active=True
        )
        
        budget.deactivate()
        assert budget.is_active is False
    
    def test_activate_budget(self):
        """测试启用预算"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            is_active=False
        )
        
        budget.activate()
        assert budget.is_active is True
    
    def test_add_item(self):
        """测试添加预算项目"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        item = BudgetItem(
            id="item1",
            budget_id="1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000")
        )
        
        budget.add_item(item)
        assert len(budget.items) == 1
        assert budget.items[0].id == "item1"
    
    def test_remove_item(self):
        """测试移除预算项目"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        item1 = BudgetItem(
            id="item1",
            budget_id="1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000")
        )
        item2 = BudgetItem(
            id="item2",
            budget_id="1",
            account_pattern="Expenses:Transport",
            amount=Decimal("500")
        )
        
        budget.add_item(item1)
        budget.add_item(item2)
        assert len(budget.items) == 2
        
        budget.remove_item("item1")
        assert len(budget.items) == 1
        assert budget.items[0].id == "item2"
    
    def test_get_total_amount(self):
        """测试获取预算总金额"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        budget.add_item(BudgetItem(
            id="item1",
            budget_id="1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000")
        ))
        budget.add_item(BudgetItem(
            id="item2",
            budget_id="1",
            account_pattern="Expenses:Transport",
            amount=Decimal("500")
        ))
        
        assert budget.get_total_amount() == 1500
    
    def test_get_total_spent(self):
        """测试获取已花费总金额"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        budget.add_item(BudgetItem(
            id="item1",
            budget_id="1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("600")
        ))
        budget.add_item(BudgetItem(
            id="item2",
            budget_id="1",
            account_pattern="Expenses:Transport",
            amount=Decimal("500"),
            spent=Decimal("200")
        ))
        
        assert budget.get_total_spent() == 800
    
    def test_get_execution_rate(self):
        """测试获取执行率"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        budget.add_item(BudgetItem(
            id="item1",
            budget_id="1",
            account_pattern="Expenses:Food",
            amount=Decimal("1000"),
            spent=Decimal("800")
        ))
        
        assert budget.get_execution_rate() == 80.0
    
    def test_get_execution_rate_with_zero_amount(self):
        """测试当预算总金额为0时获取执行率"""
        budget = Budget(
            id="1",
            user_id="user1",
            name="预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        assert budget.get_execution_rate() == 0.0
