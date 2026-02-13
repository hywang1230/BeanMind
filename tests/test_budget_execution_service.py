"""预算执行服务单元测试"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from backend.domain.budget.entities.budget import Budget, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.domain.budget.value_objects.budget_execution import BudgetStatus
from backend.domain.transaction.entities.transaction import Transaction
from backend.domain.transaction.entities.posting import Posting


@pytest.fixture
def mock_transaction_repository():
    """创建模拟交易仓储"""
    return Mock()


@pytest.fixture
def budget_execution_service(mock_transaction_repository):
    """创建预算执行服务实例"""
    return BudgetExecutionService(mock_transaction_repository)


@pytest.fixture
def sample_budget():
    """创建示例预算"""
    budget = Budget(
        id="budget1",
        user_id="user1",
        name="月度预算",
        period_type=PeriodType.MONTHLY,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        is_active=True
    )
    
    item1 = BudgetItem(
        id="item1",
        budget_id="budget1",
        account_pattern="Expenses:Food*",
        amount=Decimal("1000"),
        currency="CNY"
    )
    item2 = BudgetItem(
        id="item2",
        budget_id="budget1",
        account_pattern="Expenses:Transport",
        amount=Decimal("500"),
        currency="CNY"
    )
    
    budget.add_item(item1)
    budget.add_item(item2)
    
    return budget


@pytest.fixture
def sample_transactions():
    """创建示例交易"""
    transactions = []
    
    # 交易1: 食品支出
    t1 = Transaction(
        id="txn1",
        date=date(2025, 1, 10),
        description="超市购物",
        postings=[
            Posting(
                account="Expenses:Food:Groceries",
                amount=Decimal("200"),
                currency="CNY"
            ),
            Posting(
                account="Assets:Cash",
                amount=Decimal("-200"),
                currency="CNY"
            )
        ]
    )
    transactions.append(t1)
    
    # 交易2: 交通支出
    t2 = Transaction(
        id="txn2",
        date=date(2025, 1, 15),
        description="地铁",
        postings=[
            Posting(
                account="Expenses:Transport",
                amount=Decimal("50"),
                currency="CNY"
            ),
            Posting(
                account="Assets:Cash",
                amount=Decimal("-50"),
                currency="CNY"
            )
        ]
    )
    transactions.append(t2)
    
    return transactions


class TestBudgetExecutionService:
    """预算执行服务测试"""
    
    def test_match_account_pattern_exact(self, budget_execution_service):
        """测试精确匹配账户模式"""
        assert budget_execution_service._match_account_pattern(
            "Expenses:Food", "Expenses:Food"
        ) is True
        assert budget_execution_service._match_account_pattern(
            "Expenses:Food:Groceries", "Expenses:Food"
        ) is False
    
    def test_match_account_pattern_wildcard(self, budget_execution_service):
        """测试通配符匹配账户模式"""
        assert budget_execution_service._match_account_pattern(
            "Expenses:Food", "Expenses:Food*"
        ) is True
        assert budget_execution_service._match_account_pattern(
            "Expenses:Food:Groceries", "Expenses:Food*"
        ) is True
        assert budget_execution_service._match_account_pattern(
            "Expenses:Transport", "Expenses:Food*"
        ) is False
    
    def test_match_account_pattern_star(self, budget_execution_service):
        """测试星号匹配"""
        assert budget_execution_service._match_account_pattern(
            "Expenses:Food", "Expenses:*"
        ) is True
        assert budget_execution_service._match_account_pattern(
            "Expenses:Transport", "Expenses:*"
        ) is True
        assert budget_execution_service._match_account_pattern(
            "Assets:Cash", "Expenses:*"
        ) is False
    
    def test_calculate_spent_for_item(
        self,
        budget_execution_service,
        sample_budget,
        sample_transactions,
        mock_transaction_repository
    ):
        """测试计算预算项目的已花费金额"""
        # 模拟仓储返回交易
        mock_transaction_repository.find_by_date_range.return_value = sample_transactions
        
        # 计算食品预算项目的花费
        item = sample_budget.items[0]  # Expenses:Food*
        spent = budget_execution_service.calculate_spent_for_item(
            budget_item=item,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        assert spent == Decimal("200")  # 只有一笔食品支出
    
    def test_calculate_budget_execution(
        self,
        budget_execution_service,
        sample_budget,
        sample_transactions,
        mock_transaction_repository
    ):
        """测试计算预算执行情况"""
        # 模拟仓储返回交易
        mock_transaction_repository.find_by_date_range.return_value = sample_transactions
        
        execution = budget_execution_service.calculate_budget_execution(sample_budget)
        
        assert execution.budget_id == "budget1"
        assert execution.budget_name == "月度预算"
        assert execution.total_amount == Decimal("1500")  # 1000 + 500
        assert execution.total_spent == Decimal("250")  # 200 + 50
        assert execution.execution_rate == pytest.approx(16.67, rel=0.1)
        assert execution.status == BudgetStatus.NORMAL
    
    def test_calculate_budget_execution_warning(
        self,
        budget_execution_service,
        sample_budget,
        mock_transaction_repository
    ):
        """测试预算执行情况达到警告状态"""
        # 创建高支出交易
        high_spending_transactions = [
            Transaction(
                id="txn1",
                date=date(2025, 1, 10),
                description="大额支出",
                postings=[
                    Posting(
                        account="Expenses:Food:Restaurant",
                        amount=Decimal("1250"),  # 1250/1500 = 83.3% > 80%
                        currency="CNY"
                    ),
                    Posting(
                        account="Assets:Cash",
                        amount=Decimal("-1250"),
                        currency="CNY"
                    )
                ]
            )
        ]
        
        mock_transaction_repository.find_by_date_range.return_value = high_spending_transactions
        
        execution = budget_execution_service.calculate_budget_execution(sample_budget)
        
        assert execution.status == BudgetStatus.WARNING
    
    def test_calculate_budget_execution_over(
        self,
        budget_execution_service,
        sample_budget,
        mock_transaction_repository
    ):
        """测试预算执行情况超支状态"""
        # 创建超支交易
        over_spending_transactions = [
            Transaction(
                id="txn1",
                date=date(2025, 1, 10),
                description="超支",
                postings=[
                    Posting(
                        account="Expenses:Food:Restaurant",
                        amount=Decimal("1600"),  # 1600/1500 = 106.7% > 100%
                        currency="CNY"
                    ),
                    Posting(
                        account="Assets:Cash",
                        amount=Decimal("-1600"),
                        currency="CNY"
                    )
                ]
            )
        ]
        
        mock_transaction_repository.find_by_date_range.return_value = over_spending_transactions
        
        execution = budget_execution_service.calculate_budget_execution(sample_budget)
        
        assert execution.status == BudgetStatus.OVER
    
    def test_calculate_all_budgets_execution(
        self,
        budget_execution_service,
        sample_budget,
        sample_transactions,
        mock_transaction_repository
    ):
        """测试计算多个预算的执行情况"""
        mock_transaction_repository.find_by_date_range.return_value = sample_transactions
        
        # 创建另一个预算
        budget2 = Budget(
            id="budget2",
            user_id="user1",
            name="年度预算",
            period_type=PeriodType.YEARLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True
        )
        
        executions = budget_execution_service.calculate_all_budgets_execution(
            [sample_budget, budget2]
        )
        
        assert len(executions) == 2
    
    def test_get_budget_summary(
        self,
        budget_execution_service,
        sample_budget,
        sample_transactions,
        mock_transaction_repository
    ):
        """测试获取预算概览"""
        mock_transaction_repository.find_by_date_range.return_value = sample_transactions
        
        summary = budget_execution_service.get_budget_summary([sample_budget])
        
        assert summary["total_budgets"] == 1
        assert summary["total_budgeted"] == 1500.0
        assert summary["total_spent"] == 250.0
        assert summary["overall_rate"] == pytest.approx(16.67, rel=0.1)
        assert summary["status_count"]["normal"] == 1
        assert summary["status_count"]["warning"] == 0
        assert summary["status_count"]["exceeded"] == 0
