"""预算执行值对象单元测试"""
import pytest
from decimal import Decimal
from backend.domain.budget.value_objects.budget_execution import BudgetExecution, BudgetStatus


class TestBudgetExecution:
    """预算执行值对象测试"""
    
    def test_calculate_normal_status(self):
        """测试计算正常状态的预算执行"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("500")
        )
        
        assert execution.budget_id == "1"
        assert execution.budget_name == "月度预算"
        assert execution.total_amount == Decimal("1000")
        assert execution.total_spent == Decimal("500")
        assert execution.execution_rate == 50.0
        assert execution.status == BudgetStatus.NORMAL
        assert execution.remaining == Decimal("500")
    
    def test_calculate_warning_status(self):
        """测试计算警告状态的预算执行"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("850")
        )
        
        assert execution.execution_rate == 85.0
        assert execution.status == BudgetStatus.WARNING
    
    def test_calculate_over_status(self):
        """测试计算超支状态的预算执行"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("1200")
        )
        
        assert execution.execution_rate == 120.0
        assert execution.status == BudgetStatus.OVER
        assert execution.remaining == Decimal("-200")
    
    def test_calculate_with_zero_amount(self):
        """测试当预算总金额为0时的计算"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("0"),
            total_spent=Decimal("0")
        )
        
        assert execution.execution_rate == 0.0
        assert execution.status == BudgetStatus.NORMAL
    
    def test_calculate_with_custom_threshold(self):
        """测试自定义警告阈值"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("750"),
            warning_threshold=70.0
        )
        
        assert execution.execution_rate == 75.0
        assert execution.status == BudgetStatus.WARNING
        assert execution.warning_threshold == 70.0
    
    def test_calculate_exactly_at_warning_threshold(self):
        """测试恰好达到警告阈值"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("800"),
            warning_threshold=80.0
        )
        
        assert execution.execution_rate == 80.0
        assert execution.status == BudgetStatus.WARNING
    
    def test_calculate_exactly_at_100_percent(self):
        """测试恰好100%使用"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("1000")
        )
        
        assert execution.execution_rate == 100.0
        assert execution.status == BudgetStatus.OVER
    
    def test_get_status_color_normal(self):
        """测试获取正常状态的颜色"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("500")
        )
        
        assert execution.get_status_color() == "green"
    
    def test_get_status_color_warning(self):
        """测试获取警告状态的颜色"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("850")
        )
        
        assert execution.get_status_color() == "orange"
    
    def test_get_status_color_over(self):
        """测试获取超支状态的颜色"""
        execution = BudgetExecution.calculate(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("1200")
        )
        
        assert execution.get_status_color() == "red"
    
    def test_remaining_property(self):
        """测试剩余预算属性"""
        execution = BudgetExecution(
            budget_id="1",
            budget_name="月度预算",
            total_amount=Decimal("1000"),
            total_spent=Decimal("300"),
            execution_rate=30.0,
            status=BudgetStatus.NORMAL
        )
        
        assert execution.remaining == Decimal("700")
