"""预算应用服务测试"""
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.application.services.budget_service import BudgetApplicationService
from backend.domain.budget.entities.budget import Budget, PeriodType, CycleType
from backend.domain.budget.entities.budget_cycle import BudgetCycle
from backend.domain.budget.entities.budget_item import BudgetItem


@pytest.mark.asyncio
async def test_get_budget_for_cyclic_budget_should_aggregate_total_amount():
    """循环预算应返回全周期聚合金额，而非单期金额。"""
    budget = Budget(
        id="budget-1",
        user_id="user-1",
        name="月度循环预算",
        amount=Decimal("1000"),
        period_type=PeriodType.CUSTOM,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        cycle_type=CycleType.MONTHLY,
        items=[
            BudgetItem(
                id="item-1",
                budget_id="budget-1",
                account_pattern="Expenses:Food:*",
                amount=Decimal("1000"),
                currency="CNY"
            )
        ]
    )

    cycles = [
        BudgetCycle(
            id="c1",
            budget_id="budget-1",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            period_number=1,
            base_amount=Decimal("1000"),
            carried_over_amount=Decimal("0"),
            total_amount=Decimal("1000"),
            spent_amount=Decimal("200")
        ),
        BudgetCycle(
            id="c2",
            budget_id="budget-1",
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            period_number=2,
            base_amount=Decimal("1000"),
            carried_over_amount=Decimal("0"),
            total_amount=Decimal("1000"),
            spent_amount=Decimal("300")
        ),
        BudgetCycle(
            id="c3",
            budget_id="budget-1",
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            period_number=3,
            base_amount=Decimal("1000"),
            carried_over_amount=Decimal("0"),
            total_amount=Decimal("1000"),
            spent_amount=Decimal("400")
        ),
    ]

    budget_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=budget),
        get_cycles_by_budget_id=AsyncMock(return_value=cycles)
    )
    execution_service = SimpleNamespace(
        transaction_repository=SimpleNamespace(find_by_date_range=lambda **_: []),
        calculate_budget_execution=lambda *_: None
    )

    service = BudgetApplicationService(budget_repo, execution_service)
    service.cyclic_budget_service.calculate_all_cycles_execution = lambda _budget, _cycles: _cycles

    dto = await service.get_budget("budget-1")

    assert dto["amount"] == 1000.0
    assert dto["total_budget"] == 3000.0
    assert dto["total_spent"] == 900.0
    assert dto["total_remaining"] == 2100.0
    assert dto["overall_usage_rate"] == 30.0
    assert "monthly_budget" in dto
    assert "monthly_spent" in dto
    assert "monthly_remaining" in dto
    assert "monthly_usage_rate" in dto


@pytest.mark.asyncio
async def test_update_budget_should_apply_cycle_fields_and_regenerate_cycles():
    """更新循环配置后，应重建周期。"""
    budget = Budget(
        id="budget-1",
        user_id="user-1",
        name="预算",
        amount=Decimal("1000"),
        period_type=PeriodType.CUSTOM,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        cycle_type=CycleType.NONE
    )

    existing_cycle = BudgetCycle(
        id="old-cycle",
        budget_id="budget-1",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        period_number=1,
        base_amount=Decimal("1000"),
        carried_over_amount=Decimal("0"),
        total_amount=Decimal("1000"),
        spent_amount=Decimal("0")
    )

    budget_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=budget),
        update=AsyncMock(side_effect=lambda b: b),
        get_cycles_by_budget_id=AsyncMock(return_value=[existing_cycle]),
        replace_cycles=AsyncMock()
    )
    execution_service = SimpleNamespace(
        transaction_repository=SimpleNamespace(find_by_date_range=lambda **_: []),
        calculate_budget_execution=lambda *_: None
    )

    service = BudgetApplicationService(budget_repo, execution_service)
    service.cyclic_budget_service.calculate_all_cycles_execution = lambda _budget, _cycles: _cycles
    dto = await service.update_budget(
        budget_id="budget-1",
        cycle_type="MONTHLY",
        carry_over_enabled=True,
        end_date="2025-03-31"
    )

    assert dto["cycle_type"] == "MONTHLY"
    assert dto["carry_over_enabled"] is True
    budget_repo.replace_cycles.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_budget_should_reject_invalid_cycle_date_range_without_replacing_cycles():
    """循环预算结束日期早于开始日期时，应拒绝更新且不覆盖已有周期。"""
    budget = Budget(
        id="budget-1",
        user_id="user-1",
        name="预算",
        amount=Decimal("1000"),
        period_type=PeriodType.CUSTOM,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        cycle_type=CycleType.MONTHLY
    )

    budget_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=budget),
        update=AsyncMock(side_effect=lambda b: b),
        get_cycles_by_budget_id=AsyncMock(return_value=[]),
        replace_cycles=AsyncMock()
    )
    execution_service = SimpleNamespace(
        transaction_repository=SimpleNamespace(find_by_date_range=lambda **_: []),
        calculate_budget_execution=lambda *_: None
    )

    service = BudgetApplicationService(budget_repo, execution_service)

    with pytest.raises(ValueError, match="开始日期不能晚于结束日期"):
        await service.update_budget(
            budget_id="budget-1",
            start_date="2025-04-01",
            end_date="2025-03-31"
        )

    budget_repo.update.assert_not_awaited()
    budget_repo.replace_cycles.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_budget_monthly_metrics_for_custom_budget_should_be_prorated():
    """跨月自定义预算应按当月重叠天数分摊预算金额。"""
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    budget = Budget(
        id="budget-custom",
        user_id="user-1",
        name="跨月预算",
        amount=Decimal("1000"),
        period_type=PeriodType.CUSTOM,
        start_date=month_start,
        end_date=month_end + timedelta(days=14),
        cycle_type=CycleType.NONE,
        items=[]
    )

    budget_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=budget)
    )
    execution_service = SimpleNamespace(
        transaction_repository=SimpleNamespace(find_by_date_range=lambda **_: []),
        calculate_budget_execution=lambda *_: None
    )

    service = BudgetApplicationService(budget_repo, execution_service)
    service._calculate_spent_for_range = lambda *_: Decimal("0")

    dto = await service.get_budget("budget-custom")

    assert dto["monthly_budget"] > 0
    assert dto["monthly_budget"] < 1000.0
    assert dto["monthly_spent"] == 0.0
