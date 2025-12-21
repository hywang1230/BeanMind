"""预算执行计算服务"""
from typing import List, Dict
from datetime import date
from decimal import Decimal
import re

from backend.domain.budget.entities.budget import Budget
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.value_objects.budget_execution import BudgetExecution
from backend.domain.transaction.repositories.transaction_repository import TransactionRepository


class BudgetExecutionService:
    """预算执行计算服务
    
    负责计算预算执行情况，包括已花费金额和执行率
    """
    
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository
    
    def _match_account_pattern(self, account_name: str, pattern: str) -> bool:
        """检查账户名是否匹配模式
        
        支持以下模式:
        - 精确匹配: "Expenses:Food"
        - 前缀匹配: "Expenses:Food*" (匹配 Expenses:Food 及其所有子账户)
        - 通配符匹配: "Expenses:*" (匹配 Expenses 下的所有账户)
        
        Args:
            account_name: 账户名称
            pattern: 匹配模式
            
        Returns:
            是否匹配
        """
        # 转换模式为正则表达式
        # * 表示匹配任意字符
        regex_pattern = pattern.replace("*", ".*")
        # ^ 表示开始，$ 表示结束
        regex_pattern = f"^{regex_pattern}$"
        
        return bool(re.match(regex_pattern, account_name))
    
    def calculate_spent_for_item(
        self,
        budget_item: BudgetItem,
        start_date: date,
        end_date: date
    ) -> Decimal:
        """计算预算项目的已花费金额
        
        Args:
            budget_item: 预算项目
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            已花费金额
        """
        # 获取日期范围内的所有交易
        transactions = self.transaction_repository.find_by_date_range(
            start_date=start_date,
            end_date=end_date
        )
        
        total_spent = Decimal("0")
        
        # 遍历交易，计算匹配账户模式的支出
        for transaction in transactions:
            for posting in transaction.postings:
                # 检查账户是否匹配模式
                if self._match_account_pattern(posting.account, budget_item.account_pattern):
                    # 只计算相同货币的金额
                    if posting.currency == budget_item.currency:
                        # 如果是支出账户（Expenses），金额为正表示支出
                        # 否则金额为负表示支出
                        if posting.account.startswith("Expenses:"):
                            if posting.amount > 0:
                                total_spent += posting.amount
                        else:
                            if posting.amount < 0:
                                total_spent += abs(posting.amount)
        
        return total_spent
    
    def calculate_budget_execution(
        self,
        budget: Budget,
        warning_threshold: float = 80.0
    ) -> BudgetExecution:
        """计算预算执行情况
        
        Args:
            budget: 预算
            warning_threshold: 警告阈值（百分比）
            
        Returns:
            预算执行情况
        """
        # 计算每个预算项目的已花费金额
        for item in budget.items:
            spent = self.calculate_spent_for_item(
                budget_item=item,
                start_date=budget.start_date,
                end_date=budget.end_date or date.today()
            )
            item.update_spent(spent)
        
        # 计算总金额和总支出
        total_amount = Decimal(str(budget.get_total_amount()))
        total_spent = Decimal(str(budget.get_total_spent()))
        
        # 使用 BudgetExecution 计算执行情况
        return BudgetExecution.calculate(
            budget_id=budget.id,
            budget_name=budget.name,
            total_amount=total_amount,
            total_spent=total_spent,
            warning_threshold=warning_threshold
        )
    
    def calculate_all_budgets_execution(
        self,
        budgets: List[Budget],
        warning_threshold: float = 80.0
    ) -> List[BudgetExecution]:
        """计算多个预算的执行情况
        
        Args:
            budgets: 预算列表
            warning_threshold: 警告阈值（百分比）
            
        Returns:
            预算执行情况列表
        """
        executions = []
        for budget in budgets:
            execution = self.calculate_budget_execution(budget, warning_threshold)
            executions.append(execution)
        
        return executions
    
    def get_budget_summary(
        self,
        budgets: List[Budget]
    ) -> Dict[str, any]:
        """获取预算概览信息
        
        Args:
            budgets: 预算列表
            
        Returns:
            预算概览，包含总预算、总支出、执行率等
        """
        total_budgeted = Decimal("0")
        total_spent = Decimal("0")
        normal_count = 0
        warning_count = 0
        over_count = 0
        
        for budget in budgets:
            execution = self.calculate_budget_execution(budget)
            
            total_budgeted += execution.total_amount
            total_spent += execution.total_spent
            
            if execution.status.value == "NORMAL":
                normal_count += 1
            elif execution.status.value == "WARNING":
                warning_count += 1
            else:  # OVER
                over_count += 1
        
        # 计算整体执行率
        if total_budgeted > 0:
            overall_rate = float((total_spent / total_budgeted) * 100)
        else:
            overall_rate = 0.0
        
        return {
            "total_budgets": len(budgets),
            "total_budgeted": float(total_budgeted),
            "total_spent": float(total_spent),
            "overall_rate": overall_rate,
            "status_count": {
                "normal": normal_count,
                "warning": warning_count,
                "over": over_count
            }
        }
