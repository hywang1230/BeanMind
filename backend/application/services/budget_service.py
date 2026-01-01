"""预算应用服务

协调领域服务和仓储，提供面向接口层的高层业务操作。
处理 DTO 转换。
"""
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import date, datetime
import uuid

from backend.domain.budget.entities.budget import Budget, PeriodType, CycleType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.entities.budget_cycle import BudgetCycle
from backend.domain.budget.repositories.budget_repository import BudgetRepository
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.domain.budget.services.cyclic_budget_service import CyclicBudgetService
from backend.domain.budget.value_objects.budget_execution import BudgetStatus


class BudgetApplicationService:
    """
    预算应用服务
    
    负责：
    - 协调领域服务和仓储
    - DTO 转换（实体 <-> 字典）
    - 提供面向接口层的操作
    """
    
    # 警告阈值（百分比）
    WARNING_THRESHOLD = 80.0
    
    def __init__(
        self,
        budget_repository: BudgetRepository,
        budget_execution_service: BudgetExecutionService
    ):
        """
        初始化应用服务

        Args:
            budget_repository: 预算仓储
            budget_execution_service: 预算执行计算服务
        """
        self.budget_repository = budget_repository
        self.budget_execution_service = budget_execution_service
        self.cyclic_budget_service = CyclicBudgetService(
            budget_execution_service.transaction_repository
        )
    
    async def create_budget(
        self,
        user_id: str,
        name: str,
        amount: float,
        period_type: str,
        start_date: str,
        end_date: Optional[str] = None,
        items: Optional[List[Dict]] = None,
        cycle_type: str = "NONE",
        carry_over_enabled: bool = False
    ) -> Dict:
        """
        创建预算

        Args:
            user_id: 用户ID
            name: 预算名称
            period_type: 周期类型
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（可选）
            items: 预算项目列表
            cycle_type: 循环类型（NONE/MONTHLY/YEARLY）
            carry_over_enabled: 是否启用预算延续

        Returns:
            预算 DTO
        """
        budget_id = str(uuid.uuid4())

        # 转换日期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        # 自动计算结束日期（如果是月度或年度）
        if not end_dt:
            end_dt = self._calculate_period_end_date(start_dt, period_type)

        # 创建预算项目实体
        budget_items = []
        if items:
            for item_data in items:
                item = BudgetItem(
                    id=str(uuid.uuid4()),
                    budget_id=budget_id,
                    account_pattern=item_data["account_pattern"],
                    amount=Decimal(str(item_data.get("amount", 0))),
                    currency=item_data.get("currency", "CNY"),
                    created_at=date.today(),
                    updated_at=date.today()
                )
                budget_items.append(item)

        # 创建预算实体
        budget = Budget(
            id=budget_id,
            user_id=user_id,
            name=name,
            amount=Decimal(str(amount)),
            period_type=PeriodType(period_type),
            start_date=start_dt,
            end_date=end_dt,
            is_active=True,
            items=budget_items,
            created_at=date.today(),
            updated_at=date.today(),
            cycle_type=CycleType(cycle_type),
            carry_over_enabled=carry_over_enabled
        )
        
        # 保存到仓储
        created_budget = await self.budget_repository.create(budget)

        # 如果是循环预算，生成周期
        if created_budget.cycle_type != CycleType.NONE:
            await self._initialize_cycles(created_budget)

        return self._budget_to_dto(created_budget)
    
    async def get_budget(self, budget_id: str) -> Optional[Dict]:
        """
        获取预算详情
        
        Args:
            budget_id: 预算ID
            
        Returns:
            预算 DTO，不存在返回 None
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None
        
        # 计算执行情况
        self._calculate_budget_execution(budget)
        
        return self._budget_to_dto(budget)
    
    async def get_budgets_by_user(
        self,
        user_id: str,
        is_active: Optional[bool] = None
    ) -> List[Dict]:
        """
        获取用户的预算列表
        
        Args:
            user_id: 用户ID
            is_active: 是否只获取活跃预算
            
        Returns:
            预算 DTO 列表
        """
        budgets = await self.budget_repository.get_by_user_id(user_id, is_active)
        
        # 计算每个预算的执行情况
        for budget in budgets:
            self._calculate_budget_execution(budget)
        
        return [self._budget_to_dto(b) for b in budgets]
    
    async def get_active_budgets_for_date(
        self,
        user_id: str,
        target_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取指定日期的活跃预算
        
        Args:
            user_id: 用户ID
            target_date: 目标日期（YYYY-MM-DD，默认今天）
            
        Returns:
            预算 DTO 列表
        """
        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            dt = date.today()
        
        budgets = await self.budget_repository.get_active_budgets_for_date(user_id, dt)
        
        # 计算每个预算的执行情况
        for budget in budgets:
            self._calculate_budget_execution(budget)
        
        return [self._budget_to_dto(b) for b in budgets]
    
    async def update_budget(
        self,
        budget_id: str,
        name: Optional[str] = None,
        amount: Optional[float] = None,
        period_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        is_active: Optional[bool] = None,
        items: Optional[List[Dict]] = None
    ) -> Optional[Dict]:
        """
        更新预算
        
        Args:
            budget_id: 预算ID
            name: 预算名称
            period_type: 周期类型
            start_date: 开始日期
            end_date: 结束日期
            is_active: 是否启用
            items: 预算项目（完整替换）
            
        Returns:
            更新后的预算 DTO
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None
        
        # 更新基本字段
        if name is not None:
            budget.name = name
        if amount is not None:
            budget.amount = Decimal(str(amount))
        if period_type is not None:
            budget.period_type = PeriodType(period_type)
        if start_date is not None:
            budget.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date is not None:
            budget.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        if is_active is not None:
            if is_active:
                budget.activate()
            else:
                budget.deactivate()
        
        # 更新预算项目（完整替换）
        if items is not None:
            budget.items = []
            for item_data in items:
                item = BudgetItem(
                    id=str(uuid.uuid4()),
                    budget_id=budget_id,
                    account_pattern=item_data["account_pattern"],
                    amount=Decimal(str(item_data.get("amount", 0))),
                    currency=item_data.get("currency", "CNY"),
                    created_at=date.today(),
                    updated_at=date.today()
                )
                budget.items.append(item)
        
        budget.updated_at = date.today()
        
        # 保存更新
        updated_budget = await self.budget_repository.update(budget)
        
        # 计算执行情况
        self._calculate_budget_execution(updated_budget)
        
        return self._budget_to_dto(updated_budget)
    
    async def delete_budget(self, budget_id: str) -> bool:
        """
        删除预算
        
        Args:
            budget_id: 预算ID
            
        Returns:
            成功返回 True
        """
        return await self.budget_repository.delete(budget_id)
    
    async def add_budget_item(
        self,
        budget_id: str,
        account_pattern: str,
        amount: float,
        currency: str = "CNY"
    ) -> Optional[Dict]:
        """
        添加预算项目
        
        Args:
            budget_id: 预算ID
            account_pattern: 账户模式
            amount: 预算金额
            currency: 货币
            
        Returns:
            更新后的预算 DTO
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None
        
        item = BudgetItem(
            id=str(uuid.uuid4()),
            budget_id=budget_id,
            account_pattern=account_pattern,
            amount=Decimal(str(amount)),
            currency=currency,
            created_at=date.today(),
            updated_at=date.today()
        )
        
        budget.add_item(item)
        budget.updated_at = date.today()
        
        updated_budget = await self.budget_repository.update(budget)
        self._calculate_budget_execution(updated_budget)
        
        return self._budget_to_dto(updated_budget)
    
    async def remove_budget_item(
        self,
        budget_id: str,
        item_id: str
    ) -> Optional[Dict]:
        """
        移除预算项目
        
        Args:
            budget_id: 预算ID
            item_id: 项目ID
            
        Returns:
            更新后的预算 DTO
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None
        
        budget.remove_item(item_id)
        budget.updated_at = date.today()
        
        updated_budget = await self.budget_repository.update(budget)
        self._calculate_budget_execution(updated_budget)
        
        return self._budget_to_dto(updated_budget)
    
    async def get_budget_summary(self, user_id: str) -> Dict:
        """
        获取预算概览
        
        Args:
            user_id: 用户ID
            
        Returns:
            预算概览 DTO
        """
        budgets = await self.budget_repository.get_by_user_id(user_id)
        
        # 计算执行情况
        for budget in budgets:
            self._calculate_budget_execution(budget)
        
        summary = self.budget_execution_service.get_budget_summary(budgets)
        
        active_count = sum(1 for b in budgets if b.is_active)
        
        return {
            "total_budgets": len(budgets),
            "active_budgets": active_count,
            "total_budgeted": summary["total_budgeted"],
            "total_spent": summary["total_spent"],
            "overall_rate": summary["overall_rate"],
            "status_count": summary["status_count"]
        }
    
    def _calculate_budget_execution(self, budget: Budget) -> None:
        """
        计算预算执行情况
        
        Args:
            budget: 预算实体
        """
        self.budget_execution_service.calculate_budget_execution(
            budget,
            self.WARNING_THRESHOLD
        )
    
    def _calculate_period_end_date(self, start_date: date, period_type: str) -> Optional[date]:
        """
        计算周期结束日期
        
        Args:
            start_date: 开始日期
            period_type: 周期类型
            
        Returns:
            结束日期
        """
        if period_type == "MONTHLY":
            # 计算月末
            if start_date.month == 12:
                return date(start_date.year + 1, 1, 1).replace(day=1) - timedelta(days=1)
            else:
                return date(start_date.year, start_date.month + 1, 1) - timedelta(days=1)
        elif period_type == "YEARLY":
            # 计算年末
            return date(start_date.year, 12, 31)
        else:
            # CUSTOM 类型需要手动指定
            return None
    
    def _get_status_from_rate(self, usage_rate: float) -> str:
        """
        根据使用率获取状态
        
        Args:
            usage_rate: 使用率（百分比）
            
        Returns:
            状态字符串
        """
        if usage_rate >= 100:
            return "exceeded"
        elif usage_rate >= self.WARNING_THRESHOLD:
            return "warning"
        else:
            return "normal"
    
    def _budget_to_dto(self, budget: Budget) -> Dict:
        """
        将预算实体转换为 DTO
        
        Args:
            budget: 预算实体
            
        Returns:
            预算 DTO
        """
        total_budget = float(budget.get_total_amount())
        total_spent = float(budget.get_total_spent())
        total_remaining = total_budget - total_spent
        overall_rate = budget.get_execution_rate()
        
        # 转换预算项目
        items_dto = []
        for item in budget.items:
            item_amount = float(item.amount)
            item_spent = float(item.spent)
            item_remaining = item_amount - item_spent
            item_rate = item.get_usage_rate()
            
            items_dto.append({
                "id": item.id,
                "budget_id": item.budget_id,
                "account_pattern": item.account_pattern,
                "amount": item_amount,
                "currency": item.currency,
                "spent": item_spent,
                "remaining": item_remaining,
                "usage_rate": item_rate,
                "status": self._get_status_from_rate(item_rate)
            })
        
        return {
            "id": budget.id,
            "name": budget.name,
            "period_type": budget.period_type.value,  # 保持原始值
            "start_date": budget.start_date.isoformat() if budget.start_date else None,
            "end_date": budget.end_date.isoformat() if budget.end_date else None,
            "is_active": budget.is_active,
            "items": items_dto,
            "total_budget": total_budget,
            "total_spent": total_spent,
            "total_remaining": total_remaining,
            "overall_usage_rate": overall_rate,
            "status": self._get_status_from_rate(overall_rate),
            "created_at": budget.created_at.isoformat() if budget.created_at else None,
            "updated_at": budget.updated_at.isoformat() if budget.updated_at else None,
            "cycle_type": budget.cycle_type.value,
            "carry_over_enabled": budget.carry_over_enabled
        }

    async def get_budget_item_transactions(
        self,
        budget_id: str,
        item_id: str
    ) -> List[Dict]:
        """
        获取预算项目的关联交易
        
        Args:
            budget_id: 预算ID
            item_id: 预算项目ID
            
        Returns:
            交易 DTO 列表
        """
        # 获取预算
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return []
            
        # 查找对应的预算项目
        target_item = None
        for item in budget.items:
            if item.id == item_id:
                target_item = item
                break
        
        if not target_item:
            return []
            
        # 获取关联交易
        start_date = budget.start_date
        end_date = budget.end_date or date.today()
        
        transactions = self.budget_execution_service.get_transactions_for_item(
            budget_item=target_item,
            start_date=start_date,
            end_date=end_date
        )
        
        return [self._transaction_to_dto(t) for t in transactions]

    def _transaction_to_dto(self, transaction) -> Dict:
        """
        将交易实体转换为 DTO

        这里简单转换必要的字段用于前端显示
        """
        postings = []
        for p in transaction.postings:
            postings.append({
                "account": p.account,
                "amount": str(p.amount),
                "currency": p.currency
            })

        return {
            "id": transaction.id,
            "date": transaction.date.isoformat(),
            "payee": transaction.payee,
            "description": transaction.description,
            "flag": transaction.flag,
            "transaction_type": transaction.detect_transaction_type().value,
            "postings": postings
        }

    # ========== 循环预算相关方法 ==========

    async def get_budget_cycles(self, budget_id: str) -> List[Dict]:
        """获取预算的所有周期

        Args:
            budget_id: 预算ID

        Returns:
            周期 DTO 列表
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return []

        cycles = await self.budget_repository.get_cycles_by_budget_id(budget_id)

        # 计算所有周期的执行情况
        cycles = self.cyclic_budget_service.calculate_all_cycles_execution(budget, cycles)

        return [self._cycle_to_dto(c) for c in cycles]

    async def get_current_budget_cycle(
        self,
        budget_id: str,
        target_date: Optional[str] = None
    ) -> Optional[Dict]:
        """获取当前周期

        Args:
            budget_id: 预算ID
            target_date: 目标日期（YYYY-MM-DD，默认今天）

        Returns:
            当前周期 DTO，不存在返回None
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None

        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        else:
            dt = date.today()

        cycles = await self.budget_repository.get_cycles_by_budget_id(budget_id)
        if not cycles:
            return None

        # 计算所有周期的执行情况
        cycles = self.cyclic_budget_service.calculate_all_cycles_execution(budget, cycles)

        current_cycle = self.cyclic_budget_service.get_current_cycle(budget, cycles, dt)
        if not current_cycle:
            return None

        return self._cycle_to_dto(current_cycle)

    async def get_budget_cycle_summary(self, budget_id: str) -> Optional[Dict]:
        """获取预算周期概览

        Args:
            budget_id: 预算ID

        Returns:
            周期概览 DTO
        """
        budget = await self.budget_repository.get_by_id(budget_id)
        if not budget:
            return None

        # 首先检查是否是循环预算
        if budget.cycle_type.value == 'NONE':
            return {
                "budget_id": budget_id,
                "is_cyclic": False,
                "message": "该预算不是循环预算"
            }

        # 获取周期记录
        cycles = await self.budget_repository.get_cycles_by_budget_id(budget_id)
        if not cycles:
            # 如果是循环预算但没有周期记录，尝试生成
            await self._initialize_cycles(budget)
            cycles = await self.budget_repository.get_cycles_by_budget_id(budget_id)
            if not cycles:
                return {
                    "budget_id": budget_id,
                    "is_cyclic": True,
                    "message": "周期生成中，请稍后查看"
                }

        # 计算所有周期的执行情况
        cycles = self.cyclic_budget_service.calculate_all_cycles_execution(budget, cycles)

        summary = self.cyclic_budget_service.get_cycle_summary(cycles)
        summary["budget_id"] = budget_id
        summary["is_cyclic"] = True

        return summary

    async def _initialize_cycles(self, budget: Budget) -> None:
        """初始化预算的周期

        Args:
            budget: 预算实体
        """
        # 生成所有周期
        cycles = self.cyclic_budget_service.generate_cycles_for_budget(budget)

        # 保存到数据库
        for cycle in cycles:
            await self.budget_repository.create_cycle(cycle)

    def _cycle_to_dto(self, cycle: BudgetCycle) -> Dict:
        """将周期实体转换为 DTO

        Args:
            cycle: 周期实体

        Returns:
            周期 DTO
        """
        return {
            "id": cycle.id,
            "budget_id": cycle.budget_id,
            "period_number": cycle.period_number,
            "period_start": cycle.period_start.isoformat(),
            "period_end": cycle.period_end.isoformat(),
            "base_amount": float(cycle.base_amount),
            "carried_over_amount": float(cycle.carried_over_amount),
            "total_amount": float(cycle.total_amount),
            "spent_amount": float(cycle.spent_amount),
            "remaining_amount": float(cycle.remaining_amount),
            "usage_rate": cycle.usage_rate,
            "status": self._get_status_from_rate(cycle.usage_rate),
            "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
            "updated_at": cycle.updated_at.isoformat() if cycle.updated_at else None
        }


# 导入 timedelta 用于日期计算
from datetime import timedelta
