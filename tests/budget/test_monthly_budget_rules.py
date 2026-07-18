from decimal import Decimal

import pytest

from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetError, MonthlyBudgetService


def service(db_session, ledger_path) -> MonthlyBudgetService:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    return MonthlyBudgetService(db_session, LedgerAggregationService(db_session, ledger_path))


def test_monthly_budget_total_and_overlap_validation(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
        "CNY",
        [
            {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"},
            {"name": "交通", "account_pattern": "Expenses:Travel", "amount": "200"},
        ],
    )
    assert saved["total"] == "300"
    assert saved["spent"] == "50"
    with pytest.raises(MonthlyBudgetError) as error:
        budgets.save(
            "2025-01",
            "CNY",
            [
                {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"},
                {"name": "外食", "account_pattern": "Expenses:Food:Dining", "amount": "10"},
            ],
        )
    assert error.value.code == "OVERLAPPING_BUDGET_PATTERN"
    assert budgets.get("2025-01", "CNY")["total"] == "300"


def test_budget_risk_refund_and_zero_amount(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
        "CNY",
        [
            {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "50"},
            {"name": "交通", "account_pattern": "Expenses:Travel", "amount": "0"},
        ],
    )
    assert saved["items"][0]["risk"] == "EXCEEDED"
    assert saved["items"][0]["usage_rate"] == "1"
    assert saved["items"][1]["usage_rate"] is None


def test_copy_previous_only_copies_configuration(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    budgets.save(
        "2024-12",
        "CNY",
        [{"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "500"}],
    )
    copied = budgets.copy_previous("2025-01", "CNY")
    assert copied["total"] == "500"
    assert copied["spent"] == "50"
    with pytest.raises(MonthlyBudgetError) as error:
        budgets.copy_previous("2025-01", "CNY")
    assert error.value.code == "MONTHLY_BUDGET_EXISTS"


def test_multi_pattern_budget_item_spent_sum_and_internal_overlap(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
        "CNY",
        [
            {
                "name": "餐饮组合",
                "account_pattern": "Expenses:Food,Expenses:Travel",
                "amount": "300",
            }
        ],
    )
    assert saved["items"][0]["account_pattern"] == "Expenses:Food,Expenses:Travel"
    # Food 50 + Travel 0 from test ledger projection for 2025-01
    assert saved["items"][0]["spent"] == "50"
    assert saved["spent"] == "50"

    with pytest.raises(MonthlyBudgetError) as error:
        budgets.save(
            "2025-01",
            "CNY",
            [
                {
                    "name": "重叠",
                    "account_pattern": "Expenses:Food,Expenses:Food:Dining",
                    "amount": "10",
                }
            ],
        )
    assert error.value.code == "OVERLAPPING_BUDGET_PATTERN"


def test_multi_pattern_cross_item_overlap_rejected(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    with pytest.raises(MonthlyBudgetError) as error:
        budgets.save(
            "2025-01",
            "CNY",
            [
                {"name": "A", "account_pattern": "Expenses:Food,Expenses:Travel", "amount": "100"},
                {"name": "B", "account_pattern": "Expenses:Travel:Taxi", "amount": "10"},
            ],
        )
    assert error.value.code == "OVERLAPPING_BUDGET_PATTERN"


def test_parse_patterns_accepts_chinese_comma() -> None:
    assert MonthlyBudgetService.parse_patterns("Expenses:Food，Expenses:Travel") == [
        "Expenses:Food",
        "Expenses:Travel",
    ]
    assert MonthlyBudgetService.format_patterns(["Expenses:Food", "Expenses:Travel"]) == (
        "Expenses:Food,Expenses:Travel"
    )
