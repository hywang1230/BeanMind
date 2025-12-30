"""预算仓储 SQLAlchemy 实现"""
from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, selectinload

from backend.domain.budget.entities.budget import Budget, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.domain.budget.repositories.budget_repository import BudgetRepository
from backend.infrastructure.persistence.db.models.budget import Budget as BudgetModel, BudgetItem as BudgetItemModel


class BudgetRepositoryImpl(BudgetRepository):
    """预算仓储 SQLAlchemy 实现"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _to_entity(self, model: BudgetModel) -> Budget:
        """将ORM模型转换为领域实体"""
        items = []
        for item_model in model.items:
            item = BudgetItem(
                id=item_model.id,
                budget_id=item_model.budget_id,
                account_pattern=item_model.account_pattern,
                amount=Decimal(str(item_model.amount)),
                currency=item_model.currency,
                spent=Decimal(str(item_model.spent)),
                created_at=item_model.created_at,
                updated_at=item_model.updated_at
            )
            items.append(item)
        
        return Budget(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            amount=Decimal(str(model.amount)),
            period_type=PeriodType(model.period_type),
            start_date=model.start_date,
            end_date=model.end_date,
            is_active=model.is_active,
            items=items,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    def _to_model(self, entity: Budget) -> BudgetModel:
        """将领域实体转换为ORM模型"""
        model = BudgetModel(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            amount=entity.amount,
            period_type=entity.period_type.value,
            start_date=entity.start_date,
            end_date=entity.end_date,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
        return model
    
    def _to_item_model(self, entity: BudgetItem) -> BudgetItemModel:
        """将预算项目实体转换为ORM模型"""
        return BudgetItemModel(
            id=entity.id,
            budget_id=entity.budget_id,
            account_pattern=entity.account_pattern,
            amount=entity.amount,
            currency=entity.currency,
            spent=entity.spent,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
    
    async def create(self, budget: Budget) -> Budget:
        """创建预算"""
        model = self._to_model(budget)
        
        # 添加预算项目
        for item in budget.items:
            item_model = self._to_item_model(item)
            model.items.append(item_model)
        
        self.session.add(model)
        self.session.flush()
        self.session.commit()
        
        # 重新查询以获取关联数据
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(BudgetModel.id == model.id)
        result = self.session.execute(stmt)
        created_model = result.scalar_one()
        
        return self._to_entity(created_model)
    
    async def get_by_id(self, budget_id: str) -> Optional[Budget]:
        """根据ID获取预算"""
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(BudgetModel.id == budget_id)
        
        result = self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_entity(model)
    
    async def get_by_user_id(self, user_id: str, is_active: Optional[bool] = None) -> List[Budget]:
        """根据用户ID获取预算列表"""
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(BudgetModel.user_id == user_id)
        
        if is_active is not None:
            stmt = stmt.where(BudgetModel.is_active == is_active)
        
        stmt = stmt.order_by(BudgetModel.start_date.desc())
        
        result = self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def get_active_budgets_for_date(self, user_id: str, target_date: date) -> List[Budget]:
        """获取指定日期的活跃预算"""
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(
            and_(
                BudgetModel.user_id == user_id,
                BudgetModel.is_active == True,
                BudgetModel.start_date <= target_date,
                (BudgetModel.end_date == None) | (BudgetModel.end_date >= target_date)
            )
        )
        
        result = self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def update(self, budget: Budget) -> Budget:
        """更新预算"""
        # 获取现有模型
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(BudgetModel.id == budget.id)
        result = self.session.execute(stmt)
        model = result.scalar_one()
        
        # 更新基本字段
        model.name = budget.name
        model.amount = budget.amount
        model.period_type = budget.period_type.value
        model.start_date = budget.start_date
        model.end_date = budget.end_date
        model.is_active = budget.is_active
        model.updated_at = budget.updated_at
        
        # 更新预算项目
        # 删除不存在的项目
        existing_item_ids = {item.id for item in budget.items}
        model.items = [item for item in model.items if item.id in existing_item_ids]
        
        # 更新或添加项目
        model_item_dict = {item.id: item for item in model.items}
        for item_entity in budget.items:
            if item_entity.id in model_item_dict:
                # 更新现有项目
                item_model = model_item_dict[item_entity.id]
                item_model.account_pattern = item_entity.account_pattern
                item_model.amount = item_entity.amount
                item_model.currency = item_entity.currency
                item_model.spent = item_entity.spent
                item_model.updated_at = item_entity.updated_at
            else:
                # 添加新项目
                item_model = self._to_item_model(item_entity)
                model.items.append(item_model)
        
        self.session.flush()
        self.session.commit()
        
        return self._to_entity(model)
    
    async def delete(self, budget_id: str) -> bool:
        """删除预算"""
        stmt = select(BudgetModel).where(BudgetModel.id == budget_id)
        result = self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return False
        
        self.session.delete(model)
        self.session.flush()
        self.session.commit()
        
        return True
    
    async def exists(self, budget_id: str) -> bool:
        """检查预算是否存在"""
        stmt = select(BudgetModel.id).where(BudgetModel.id == budget_id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def find_by_date_range(self, start_date: date, end_date: date) -> List[Budget]:
        """查找指定日期范围内有效的预算"""
        stmt = select(BudgetModel).options(
            selectinload(BudgetModel.items)
        ).where(
            and_(
                BudgetModel.start_date <= end_date,
                (BudgetModel.end_date == None) | (BudgetModel.end_date >= start_date)
            )
        )
        
        result = self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
