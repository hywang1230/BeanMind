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
