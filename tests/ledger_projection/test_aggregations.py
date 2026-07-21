from decimal import Decimal

import pytest

from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionDirtyError,
    LedgerProjectionService,
)
from backend.services.ledger_aggregation import LedgerAggregationService, shift_month


def test_monthly_aggregation_preserves_decimal_and_refund(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    assert aggregation.monthly_pattern_totals("2024-12", "Expenses:Food") == {
        "CNY": Decimal("123.456789123456789")
    }
    assert aggregation.monthly_flows("2025-01") == {
        "expense": {"CNY": Decimal("50")},
        "income": {"CNY": Decimal("10000")},
    }


def test_prefix_escaping_and_overlap_rules(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    assert aggregation.monthly_pattern_totals("2025-01", "Expenses:Food") == {
        "CNY": Decimal("50")
    }
    assert aggregation.monthly_pattern_totals("2025-01", "Expenses:Food%") == {}
    assert aggregation.patterns_overlap("Expenses:Food", "Expenses:Food:Dining")
    assert not aggregation.patterns_overlap("Expenses:Food", "Expenses:Travel")


def test_dirty_projection_blocks_aggregation(db_session, ledger_path) -> None:
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, RuntimeError("broken"))
    with pytest.raises(LedgerProjectionDirtyError):
        LedgerAggregationService(db_session, ledger_path).monthly_flows("2025-01")


def test_monthly_cashflow_range_groups_months_and_cross_year(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    result = aggregation.monthly_cashflow_by_currency("2024-12", "2025-02")

    assert list(result.keys()) == ["2024-12", "2025-01", "2025-02"]
    assert result["2024-12"]["expense"]["CNY"] == Decimal("131.456789123456789")
    assert result["2024-12"]["income"] == {}
    assert result["2025-01"]["income"]["CNY"] == Decimal("10000")
    assert result["2025-01"]["expense"]["CNY"] == Decimal("50")
    assert result["2025-02"]["expense"]["USD"] == Decimal("99.990000000000001")


def test_monthly_cashflow_fills_empty_months(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    result = aggregation.monthly_cashflow_by_currency("2024-09", "2024-11")
    assert list(result.keys()) == ["2024-09", "2024-10", "2024-11"]
    for month in result.values():
        assert month == {"income": {}, "expense": {}}


def test_monthly_cashflow_dirty_blocks_range(db_session, ledger_path) -> None:
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, RuntimeError("broken"))
    with pytest.raises(LedgerProjectionDirtyError):
        LedgerAggregationService(db_session, ledger_path).monthly_cashflow_by_currency(
            "2024-12", "2025-01"
        )


def test_shift_month_helpers() -> None:
    assert shift_month("2025-01", -11) == "2024-02"
    assert shift_month("2024-03", 10) == "2025-01"


def test_frequent_items_uses_projection_aggregation(db_session, ledger_path) -> None:
    from datetime import date

    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)

    expenses = aggregation.frequent_items(
        item_type="expense",
        start=date(2024, 1, 1),
        end=date(2025, 12, 31),
        limit=3,
    )
    # Food 与 Travel 均为 2 次；同频次时按 last_used 降序，Travel 更新
    assert expenses[0] == {
        "name": "Expenses:Travel",
        "count": 2,
        "last_used": "2025-02-01",
    }
    assert expenses[1] == {
        "name": "Expenses:Food",
        "count": 2,
        "last_used": "2025-01-15",
    }

    accounts = aggregation.frequent_items(
        item_type="account",
        start=date(2024, 1, 1),
        end=date(2025, 12, 31),
        limit=3,
    )
    assert accounts[0]["name"] == "Assets:Cash"
    assert accounts[0]["count"] == 4

    income = aggregation.frequent_items(
        item_type="income",
        start=date(2025, 1, 1),
        end=date(2025, 1, 31),
        limit=3,
    )
    assert income == [
        {"name": "Income:Salary", "count": 1, "last_used": "2025-01-15"}
    ]


def test_frequent_items_dirty_projection_blocked(db_session, ledger_path) -> None:
    from datetime import date

    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, RuntimeError("broken"))
    with pytest.raises(LedgerProjectionDirtyError):
        LedgerAggregationService(db_session, ledger_path).frequent_items(
            item_type="expense",
            start=date(2024, 1, 1),
            end=date(2025, 12, 31),
            limit=3,
        )


def test_daily_cashflow_fills_month_and_excludes_transfers(db_session, ledger_path) -> None:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)

    result = aggregation.daily_cashflow_by_currency("2025-01")
    assert list(result.keys()) == [f"2025-01-{day:02d}" for day in range(1, 32)]
    assert result["2025-01-01"] == {
        "income": {},
        "expense": {},
        "has_activity": False,
    }
    # salary + lunch same day
    assert result["2025-01-15"]["has_activity"] is True
    assert result["2025-01-15"]["income"]["CNY"] == Decimal("10000")
    assert result["2025-01-15"]["expense"]["CNY"] == Decimal("50")

    # August transfer-only activity must not appear as income/expense days
    august = aggregation.daily_cashflow_by_currency("2024-08")
    assert all(day["has_activity"] is False for day in august.values())
    assert all(day["income"] == {} and day["expense"] == {} for day in august.values())


def test_daily_cashflow_preserves_refund_sign_and_zero_cancel(db_session, ledger_path, tmp_path) -> None:
    # Extend projection fixture with refund and zero cancel-out day.
    ledger_dir = ledger_path.parent
    extra = ledger_dir / "transactions_2025.beancount"
    extra.write_text(
        extra.read_text(encoding="utf-8")
        + """
2025-01-20 * "退款" "餐厅退款"
  Expenses:Food  -20 CNY
  Assets:Cash     20 CNY

2025-01-21 * "冲销对冲" "同日正负抵消"
  Expenses:Travel  15 CNY
  Assets:Cash     -15 CNY

2025-01-21 * "冲销对冲" "同日正负抵消回冲"
  Expenses:Travel  -15 CNY
  Assets:Cash      15 CNY
""",
        encoding="utf-8",
    )
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    aggregation = LedgerAggregationService(db_session, ledger_path)
    result = aggregation.daily_cashflow_by_currency("2025-01")

    # lunch 50 + refund -20
    assert result["2025-01-15"]["expense"]["CNY"] == Decimal("50")
    assert result["2025-01-20"]["has_activity"] is True
    assert result["2025-01-20"]["expense"]["CNY"] == Decimal("-20")

    # cancel-out day still has activity with zero expense
    assert result["2025-01-21"]["has_activity"] is True
    assert result["2025-01-21"]["expense"].get("CNY", Decimal("0")) == Decimal("0")


def test_daily_cashflow_dirty_blocks(db_session, ledger_path) -> None:
    projection = LedgerProjectionService(db_session, ledger_path)
    projection.rebuild_all()
    projection.mark_dirty(ledger_path, RuntimeError("broken"))
    with pytest.raises(LedgerProjectionDirtyError):
        LedgerAggregationService(db_session, ledger_path).daily_cashflow_by_currency("2025-01")
