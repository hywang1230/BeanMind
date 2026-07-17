from decimal import Decimal

import pytest

from backend.infrastructure.persistence.ledger_projection import (
    LedgerProjectionDirtyError,
    LedgerProjectionService,
)
from backend.services.ledger_aggregation import LedgerAggregationService


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
