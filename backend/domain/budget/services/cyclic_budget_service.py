"""循环预算计算服务"""
from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal
from calendar import monthrange

from backend.domain.budget.entities.budget import Budget, CycleType
from backend.domain.budget.entities.budget_cycle import BudgetCycle
from backend.domain.transaction.repositories.transaction_repository import TransactionRepository


class CyclicBudgetService:
    """循环预算计算服务

    负责：
    - 生成预算周期
    - 计算周期执行情况
    - 处理预算延续
    """

    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def generate_cycles_for_budget(self, budget: Budget) -> List[BudgetCycle]:
        """为预算生成所有周期

        Args:
            budget: 预算实体

        Returns:
            预算周期列表
        """
        if budget.cycle_type == CycleType.NONE:
            return []

        if not budget.end_date:
            return []

        cycles = []
        current_start = budget.start_date
        period_number = 1
        is_first_period = True  # 标记是否为第一个周期

        # 生成周期直到预算结束日期
        while current_start <= budget.end_date:
            if budget.cycle_type == CycleType.MONTHLY:
                # 按月生成周期
                year = current_start.year
                month = current_start.month

                # 计算月末
                last_day = monthrange(year, month)[1]
                period_end = date(year, month, last_day)

                # 只有第一个周期才需要检查budget.end_date
                if is_first_period and period_end > budget.end_date:
                    period_end = budget.end_date

                # 如果周期结束日期超过预算结束日期，使用预算结束日期
                if period_end > budget.end_date:
                    period_end = budget.end_date

            elif budget.cycle_type == CycleType.YEARLY:
                # 按年生成周期
                # 计算年末
                period_end = date(current_start.year, 12, 31)

                # 只有第一个周期才需要检查budget.end_date
                if is_first_period and period_end > budget.end_date:
                    period_end = budget.end_date

                # 如果周期结束日期超过预算结束日期，使用预算结束日期
                if period_end > budget.end_date:
                    period_end = budget.end_date
            else:
                break

            # 验证日期有效性
            if period_end < current_start:
                # 跳过无效周期
                break

            # 创建周期
            cycle = BudgetCycle(
                id=f"{budget.id}_cycle_{period_number}",
                budget_id=budget.id,
                period_start=current_start,
                period_end=period_end,
                period_number=period_number,
                base_amount=budget.amount,
                carried_over_amount=Decimal("0"),
                total_amount=budget.amount,
                spent_amount=Decimal("0"),
                created_at=date.today(),
                updated_at=date.today()
            )
            cycles.append(cycle)

            # 标记第一个周期已处理
            is_first_period = False

            # 移动到下一个周期
            if budget.cycle_type == CycleType.MONTHLY:
                # 下个月第一天
                if period_end.month == 12:
                    current_start = date(period_end.year + 1, 1, 1)
                else:
                    current_start = date(period_end.year, period_end.month + 1, 1)
            elif budget.cycle_type == CycleType.YEARLY:
                # 下一年第一天
                current_start = date(period_end.year + 1, 1, 1)
            else:
                break

            period_number += 1

        return cycles

    def calculate_cycle_execution(
        self,
        cycle: BudgetCycle,
        budget: Budget,
        previous_cycle: Optional[BudgetCycle] = None
    ) -> BudgetCycle:
        """计算周期的执行情况

        Args:
            cycle: 预算周期
            budget: 预算实体
            previous_cycle: 上一个周期（用于延续计算）

        Returns:
            更新后的周期
        """
        today = date.today()
        
        # 计算延续金额
        # 重要：只有当上一个周期已经结束时，才计算延续金额
        # 未来周期不应该基于预测的剩余金额计算延续
        if budget.carry_over_enabled and previous_cycle:
            # 只有上一个周期已经结束，才使用其剩余金额
            if previous_cycle.period_end < today:
                cycle.carried_over_amount = previous_cycle.carry_forward_amount
            else:
                # 上一个周期还未结束，延续金额为0
                cycle.carried_over_amount = Decimal("0")
        else:
            cycle.carried_over_amount = Decimal("0")

        # 计算总金额
        cycle.total_amount = cycle.base_amount + cycle.carried_over_amount

        # 计算已花费金额
        spent = self._calculate_spent_for_period(
            budget=budget,
            start_date=cycle.period_start,
            end_date=cycle.period_end
        )
        cycle.spent_amount = spent

        return cycle

    def calculate_all_cycles_execution(
        self,
        budget: Budget,
        existing_cycles: List[BudgetCycle]
    ) -> List[BudgetCycle]:
        """计算所有周期的执行情况

        Args:
            budget: 预算实体
            existing_cycles: 已存在的周期列表

        Returns:
            更新后的周期列表
        """
        if not existing_cycles:
            return existing_cycles

        # 按周期序号排序
        sorted_cycles = sorted(existing_cycles, key=lambda c: c.period_number)

        # 计算每个周期的执行情况
        for i, cycle in enumerate(sorted_cycles):
            previous_cycle = sorted_cycles[i - 1] if i > 0 else None
            self.calculate_cycle_execution(cycle, budget, previous_cycle)

        return sorted_cycles

    def get_current_cycle(
        self,
        budget: Budget,
        cycles: List[BudgetCycle],
        target_date: Optional[date] = None
    ) -> Optional[BudgetCycle]:
        """获取当前周期

        Args:
            budget: 预算实体
            cycles: 周期列表
            target_date: 目标日期（默认今天）

        Returns:
            当前周期，不存在返回None
        """
        if target_date is None:
            target_date = date.today()

        for cycle in cycles:
            if cycle.period_start <= target_date <= cycle.period_end:
                return cycle

        return None

    def get_cycle_summary(
        self,
        cycles: List[BudgetCycle]
    ) -> dict:
        """获取周期概览

        Args:
            cycles: 周期列表

        Returns:
            周期概览
        """
        if not cycles:
            return {
                "total_cycles": 0,
                "total_base_amount": 0.0,
                "total_carried_over": 0.0,
                "total_amount": 0.0,
                "total_spent": 0.0,
                "total_remaining": 0.0,
                "completed_cycles": 0,
                "current_cycle": None
            }

        total_base = sum((c.base_amount for c in cycles), Decimal("0"))
        total_carried = sum((c.carried_over_amount for c in cycles), Decimal("0"))
        total_amount = sum((c.total_amount for c in cycles), Decimal("0"))
        total_spent = sum((c.spent_amount for c in cycles), Decimal("0"))
        total_remaining = sum((c.remaining_amount for c in cycles), Decimal("0"))

        today = date.today()
        current_cycle = self._find_current_cycle(cycles, today)
        completed_cycles = sum(1 for c in cycles if c.period_end < today)

        return {
            "total_cycles": len(cycles),
            "total_base_amount": float(total_base),
            "total_carried_over": float(total_carried),
            "total_amount": float(total_amount),
            "total_spent": float(total_spent),
            "total_remaining": float(total_remaining),
            "completed_cycles": completed_cycles,
            "current_cycle": {
                "period_number": current_cycle.period_number,
                "period_start": current_cycle.period_start.isoformat(),
                "period_end": current_cycle.period_end.isoformat(),
                "total_amount": float(current_cycle.total_amount),
                "spent_amount": float(current_cycle.spent_amount),
                "remaining_amount": float(current_cycle.remaining_amount),
                "usage_rate": current_cycle.usage_rate
            } if current_cycle else None
        }

    def _calculate_spent_for_period(
        self,
        budget: Budget,
        start_date: date,
        end_date: date
    ) -> Decimal:
        """计算指定时期的已花费金额

        Args:
            budget: 预算实体
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            已花费金额
        """
        total_spent = Decimal("0")

        # 遍历所有预算项目
        for item in budget.items:
            # 获取该项目的花费
            item_spent = self._calculate_spent_for_item(
                item=item,
                start_date=start_date,
                end_date=end_date
            )
            total_spent += item_spent

        return total_spent

    def _calculate_spent_for_item(
        self,
        item,
        start_date: date,
        end_date: date
    ) -> Decimal:
        """计算预算项目在指定时期的已花费金额

        Args:
            item: 预算项目
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            已花费金额
        """
        from backend.domain.budget.services.budget_execution_service import BudgetExecutionService

        # 使用现有的执行计算服务
        execution_service = BudgetExecutionService(self.transaction_repository)
        return execution_service.calculate_spent_for_item(item, start_date, end_date)

    def _find_current_cycle(
        self,
        cycles: List[BudgetCycle],
        target_date: date
    ) -> Optional[BudgetCycle]:
        """查找当前周期

        Args:
            cycles: 周期列表
            target_date: 目标日期

        Returns:
            当前周期，不存在返回None
        """
        for cycle in cycles:
            if cycle.period_start <= target_date <= cycle.period_end:
                return cycle
        return None
