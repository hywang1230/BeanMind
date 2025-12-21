"""预算仓储实现单元测试"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.domain.budget.entities.budget import Budget, PeriodType
from backend.domain.budget.entities.budget_item import BudgetItem
from backend.infrastructure.persistence.db.models.base import Base
from backend.infrastructure.persistence.db.repositories.budget_repository_impl import BudgetRepositoryImpl
import uuid


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def budget_repository(db_session):
    """创建预算仓储实例"""
    return BudgetRepositoryImpl(db_session)


@pytest.fixture
def sample_budget():
    """创建示例预算"""
    budget = Budget(
        id=str(uuid.uuid4()),
        user_id="user1",
        name="月度预算",
        period_type=PeriodType.MONTHLY,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        is_active=True
    )
    
    item1 = BudgetItem(
        id=str(uuid.uuid4()),
        budget_id=budget.id,
        account_pattern="Expenses:Food",
        amount=Decimal("1000"),
        currency="CNY"
    )
    item2 = BudgetItem(
        id=str(uuid.uuid4()),
        budget_id=budget.id,
        account_pattern="Expenses:Transport",
        amount=Decimal("500"),
        currency="CNY"
    )
    
    budget.add_item(item1)
    budget.add_item(item2)
    
    return budget


@pytest.mark.asyncio
class TestBudgetRepositoryImpl:
    """预算仓储实现测试"""
    
    async def test_create_budget(self, budget_repository, sample_budget):
        """测试创建预算"""
        created_budget = await budget_repository.create(sample_budget)
        
        assert created_budget.id == sample_budget.id
        assert created_budget.name == "月度预算"
        assert created_budget.period_type == PeriodType.MONTHLY
        assert len(created_budget.items) == 2
    
    async def test_get_by_id(self, budget_repository, sample_budget):
        """测试根据ID获取预算"""
        await budget_repository.create(sample_budget)
        
        budget = await budget_repository.get_by_id(sample_budget.id)
        
        assert budget is not None
        assert budget.id == sample_budget.id
        assert budget.name == "月度预算"
        assert len(budget.items) == 2
    
    async def test_get_by_id_not_found(self, budget_repository):
        """测试根据不存在的ID获取预算"""
        budget = await budget_repository.get_by_id("nonexistent")
        assert budget is None
    
    async def test_get_by_user_id(self, budget_repository, sample_budget):
        """测试根据用户ID获取预算列表"""
        await budget_repository.create(sample_budget)
        
        # 创建另一个预算
        budget2 = Budget(
            id=str(uuid.uuid4()),
            user_id="user1",
            name="年度预算",
            period_type=PeriodType.YEARLY,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True
        )
        await budget_repository.create(budget2)
        
        budgets = await budget_repository.get_by_user_id("user1")
        
        assert len(budgets) == 2
    
    async def test_get_by_user_id_with_active_filter(self, budget_repository, sample_budget):
        """测试根据用户ID和活跃状态获取预算列表"""
        await budget_repository.create(sample_budget)
        
        # 创建一个非活跃预算
        budget2 = Budget(
            id=str(uuid.uuid4()),
            user_id="user1",
            name="已停用预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2024, 12, 1),
            end_date=date(2024, 12, 31),
            is_active=False
        )
        await budget_repository.create(budget2)
        
        active_budgets = await budget_repository.get_by_user_id("user1", is_active=True)
        
        assert len(active_budgets) == 1
        assert active_budgets[0].is_active is True
    
    async def test_get_active_budgets_for_date(self, budget_repository, sample_budget):
        """测试获取指定日期的活跃预算"""
        await budget_repository.create(sample_budget)
        
        # 创建一个不在日期范围内的预算
        budget2 = Budget(
            id=str(uuid.uuid4()),
            user_id="user1",
            name="2月预算",
            period_type=PeriodType.MONTHLY,
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 28),
            is_active=True
        )
        await budget_repository.create(budget2)
        
        budgets = await budget_repository.get_active_budgets_for_date("user1", date(2025, 1, 15))
        
        assert len(budgets) == 1
        assert budgets[0].name == "月度预算"
    
    async def test_update_budget(self, budget_repository, sample_budget):
        """测试更新预算"""
        created_budget = await budget_repository.create(sample_budget)
        
        # 更新预算
        created_budget.name = "更新后的月度预算"
        created_budget.items[0].amount = Decimal("1200")
        
        updated_budget = await budget_repository.update(created_budget)
        
        assert updated_budget.name == "更新后的月度预算"
        assert updated_budget.items[0].amount == Decimal("1200")
    
    async def test_update_budget_add_item(self, budget_repository, sample_budget):
        """测试更新预算时添加项目"""
        created_budget = await budget_repository.create(sample_budget)
        
        # 添加新项目
        new_item = BudgetItem(
            id=str(uuid.uuid4()),
            budget_id=created_budget.id,
            account_pattern="Expenses:Entertainment",
            amount=Decimal("300"),
            currency="CNY"
        )
        created_budget.add_item(new_item)
        
        updated_budget = await budget_repository.update(created_budget)
        
        assert len(updated_budget.items) == 3
    
    async def test_update_budget_remove_item(self, budget_repository, sample_budget):
        """测试更新预算时移除项目"""
        created_budget = await budget_repository.create(sample_budget)
        
        # 移除一个项目
        item_to_remove = created_budget.items[0].id
        created_budget.remove_item(item_to_remove)
        
        updated_budget = await budget_repository.update(created_budget)
        
        assert len(updated_budget.items) == 1
    
    async def test_delete_budget(self, budget_repository, sample_budget):
        """测试删除预算"""
        created_budget = await budget_repository.create(sample_budget)
        
        result = await budget_repository.delete(created_budget.id)
        
        assert result is True
        
        # 验证已删除
        budget = await budget_repository.get_by_id(created_budget.id)
        assert budget is None
    
    async def test_delete_nonexistent_budget(self, budget_repository):
        """测试删除不存在的预算"""
        result = await budget_repository.delete("nonexistent")
        assert result is False
    
    async def test_exists(self, budget_repository, sample_budget):
        """测试检查预算是否存在"""
        created_budget = await budget_repository.create(sample_budget)
        
        assert await budget_repository.exists(created_budget.id) is True
        assert await budget_repository.exists("nonexistent") is False
