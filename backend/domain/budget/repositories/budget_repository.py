"""预算仓储接口"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import date
from backend.domain.budget.entities.budget import Budget
from backend.domain.budget.entities.budget_cycle import BudgetCycle


class BudgetRepository(ABC):
    """预算仓储接口"""
    
    @abstractmethod
    async def create(self, budget: Budget) -> Budget:
        """创建预算
        
        Args:
            budget: 预算实体
            
        Returns:
            创建后的预算实体
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, budget_id: str) -> Optional[Budget]:
        """根据ID获取预算
        
        Args:
            budget_id: 预算ID
            
        Returns:
            预算实体，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    async def get_by_user_id(self, user_id: str, is_active: Optional[bool] = None) -> List[Budget]:
        """根据用户ID获取预算列表
        
        Args:
            user_id: 用户ID
            is_active: 是否只获取活跃的预算，None表示获取所有
            
        Returns:
            预算实体列表
        """
        pass
    
    @abstractmethod
    async def get_active_budgets_for_date(self, user_id: str, target_date: date) -> List[Budget]:
        """获取指定日期的活跃预算
        
        Args:
            user_id: 用户ID
            target_date: 目标日期
            
        Returns:
            预算实体列表
        """
        pass
    
    @abstractmethod
    async def update(self, budget: Budget) -> Budget:
        """更新预算
        
        Args:
            budget: 预算实体
            
        Returns:
            更新后的预算实体
        """
        pass
    
    @abstractmethod
    async def delete(self, budget_id: str) -> bool:
        """删除预算
        
        Args:
            budget_id: 预算ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        pass
    
    @abstractmethod
    async def exists(self, budget_id: str) -> bool:
        """检查预算是否存在
        
        Args:
            budget_id: 预算ID
            
        Returns:
            存在返回True，否则返回False
        """
        pass

    @abstractmethod
    async def find_by_date_range(self, start_date: date, end_date: date) -> List[Budget]:
        """查找指定日期范围内有效的预算

        只有预算的时间与此时间有交叉，即为符合的预算（相交、包含都行）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            预算实体列表
        """
        pass

    # BudgetCycle 相关方法
    @abstractmethod
    async def create_cycle(self, cycle: BudgetCycle) -> BudgetCycle:
        """创建预算周期

        Args:
            cycle: 周期实体

        Returns:
            创建后的周期实体
        """
        pass

    @abstractmethod
    async def get_cycles_by_budget_id(self, budget_id: str) -> List[BudgetCycle]:
        """获取预算的所有周期

        Args:
            budget_id: 预算ID

        Returns:
            周期实体列表
        """
        pass

    @abstractmethod
    async def get_cycles_by_budget_ids(self, budget_ids: List[str]) -> Dict[str, List[BudgetCycle]]:
        """批量获取多个预算的周期

        Args:
            budget_ids: 预算ID列表

        Returns:
            budget_id -> 周期列表
        """
        pass

    @abstractmethod
    async def get_cycle_by_id(self, cycle_id: str) -> Optional[BudgetCycle]:
        """根据ID获取周期

        Args:
            cycle_id: 周期ID

        Returns:
            周期实体，不存在返回None
        """
        pass

    @abstractmethod
    async def update_cycle(self, cycle: BudgetCycle) -> BudgetCycle:
        """更新周期

        Args:
            cycle: 周期实体

        Returns:
            更新后的周期实体
        """
        pass

    @abstractmethod
    async def delete_cycle(self, cycle_id: str) -> bool:
        """删除周期

        Args:
            cycle_id: 周期ID

        Returns:
            删除成功返回True
        """
        pass

    @abstractmethod
    async def replace_cycles(self, budget_id: str, cycles: List[BudgetCycle]) -> None:
        """原子替换预算的全部周期

        Args:
            budget_id: 预算ID
            cycles: 新周期列表
        """
        pass

    @abstractmethod
    async def get_current_cycle(
        self,
        budget_id: str,
        target_date: date
    ) -> Optional[BudgetCycle]:
        """获取当前周期

        Args:
            budget_id: 预算ID
            target_date: 目标日期

        Returns:
            当前周期，不存在返回None
        """
        pass
