from datetime import date
from decimal import Decimal

import pytest

from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService
from backend.infrastructure.persistence.db.models import MonthlyBudget
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetError, MonthlyBudgetService


class FakeBeancountService:
    def __init__(self, rates: dict[str, Decimal] | None = None) -> None:
        self.rates = rates or {}
        self.requested_dates: list[date] = []

    def get_operating_currency(self) -> str:
        return "CNY"

    def get_all_exchange_rates(self, to_currency: str, as_of_date: date):
        assert to_currency == "CNY"
        self.requested_dates.append(as_of_date)
        return self.rates


def service(
    db_session,
    ledger_path,
    beancount_service: FakeBeancountService | None = None,
) -> MonthlyBudgetService:
    LedgerProjectionService(db_session, ledger_path).rebuild_all()
    return MonthlyBudgetService(
        db_session,
        LedgerAggregationService(db_session, ledger_path),
        beancount_service or FakeBeancountService(),
    )


def test_monthly_budget_total_and_overlap_validation(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
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
            [
                {"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "100"},
                {"name": "外食", "account_pattern": "Expenses:Food:Dining", "amount": "10"},
            ],
        )
    assert error.value.code == "OVERLAPPING_BUDGET_PATTERN"
    assert budgets.get("2025-01")["total"] == "300"


def test_budget_risk_refund_and_zero_amount(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
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
        [{"name": "餐饮", "account_pattern": "Expenses:Food", "amount": "500"}],
    )
    copied = budgets.copy_previous("2025-01")
    assert copied["total"] == "500"
    assert copied["spent"] == "50"
    with pytest.raises(MonthlyBudgetError) as error:
        budgets.copy_previous("2025-01")
    assert error.value.code == "MONTHLY_BUDGET_EXISTS"


def test_multi_pattern_budget_item_spent_sum_and_internal_overlap(db_session, ledger_path) -> None:
    budgets = service(db_session, ledger_path)
    saved = budgets.save(
        "2025-01",
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


def test_budget_converts_all_currencies_with_month_end_rate_and_decimal(
    db_session, ledger_path
) -> None:
    beancount = FakeBeancountService({"USD": Decimal("7.250000000")})
    budgets = service(db_session, ledger_path, beancount)

    saved = budgets.save(
        "2025-02",
        [{"name": "差旅", "account_pattern": "Expenses:Travel", "amount": "800"}],
    )

    assert saved["currency"] == "CNY"
    assert Decimal(saved["spent"]) == Decimal("724.92750000000000725")
    assert Decimal(saved["items"][0]["remaining"]) == Decimal("75.07249999999999275")
    assert beancount.requested_dates == [date(2025, 2, 28)]


def test_budget_converts_foreign_currency_refund(db_session, ledger_path) -> None:
    transactions = ledger_path.parent / "transactions_2025.beancount"
    transactions.write_text(
        transactions.read_text(encoding="utf-8")
        + """

2025-02-10 * "酒店" "住宿退款"
  Expenses:Travel  -9.990000000000001 USD
  Assets:Broker     9.990000000000001 USD
""",
        encoding="utf-8",
    )
    budgets = service(
        db_session,
        ledger_path,
        FakeBeancountService({"USD": Decimal("7.250000000")}),
    )

    saved = budgets.save(
        "2025-02",
        [{"name": "差旅", "account_pattern": "Expenses:Travel", "amount": "800"}],
    )

    assert Decimal(saved["spent"]) == Decimal("652.500000000000000")


def test_budget_missing_exchange_rate_does_not_save_partial_result(
    db_session, ledger_path
) -> None:
    budgets = service(db_session, ledger_path, FakeBeancountService())

    with pytest.raises(MonthlyBudgetError) as error:
        budgets.save(
            "2025-02",
            [{"name": "差旅", "account_pattern": "Expenses:Travel", "amount": "800"}],
        )

    assert error.value.code == "MISSING_EXCHANGE_RATE"
    assert error.value.details == {
        "month": "2025-02",
        "operating_currency": "CNY",
        "currencies": ["USD"],
    }
    assert db_session.query(MonthlyBudget).count() == 0
