from datetime import date
from decimal import Decimal

from backend.domain.analysis.monthly_report_facts_service import MonthlyReportFactsService
from backend.domain.transaction.entities.posting import Posting
from backend.domain.transaction.entities.transaction import Transaction


def build_transaction(txn_date: date, description: str, postings, payee=None, tags=None):
    return Transaction(
        date=txn_date,
        description=description,
        payee=payee,
        postings=postings,
        tags=set(tags or []),
    )


def test_build_facts_excludes_transfer_and_tracks_investment():
    service = MonthlyReportFactsService()

    income = build_transaction(
        date(2026, 4, 1),
        "工资",
        [
            Posting(account="Assets:Bank", amount=Decimal("10000"), currency="CNY"),
            Posting(account="Income:Salary", amount=Decimal("-10000"), currency="CNY"),
        ],
        payee="公司",
    )
    expense = build_transaction(
        date(2026, 4, 2),
        "房租",
        [
            Posting(account="Expenses:Housing", amount=Decimal("3000"), currency="CNY"),
            Posting(account="Assets:Bank", amount=Decimal("-3000"), currency="CNY"),
        ],
        tags={"fixed"},
    )
    transfer = build_transaction(
        date(2026, 4, 3),
        "内部转账",
        [
            Posting(account="Assets:Bank", amount=Decimal("500"), currency="CNY"),
            Posting(account="Assets:Cash", amount=Decimal("-500"), currency="CNY"),
        ],
    )
    investment = build_transaction(
        date(2026, 4, 4),
        "基金买入",
        [
            Posting(account="Assets:Investment:Fund", amount=Decimal("2000"), currency="CNY"),
            Posting(account="Assets:Bank", amount=Decimal("-2000"), currency="CNY"),
        ],
        tags={"investment"},
    )

    facts = service.build_facts(
        report_month="2026-04",
        current_transactions=[income, expense, transfer, investment],
        previous_transactions=[],
        recent_average_transactions=[],
        current_balances={
            "Assets:Bank": {"CNY": Decimal("7000")},
            "Assets:Investment:Fund": {"CNY": Decimal("2100")},
        },
        previous_balances={
            "Assets:Bank": {"CNY": Decimal("0")},
            "Assets:Investment:Fund": {"CNY": Decimal("0")},
        },
    )

    assert facts["summary_metrics"]["income"] == "10000.00"
    assert facts["summary_metrics"]["expense"] == "3000.00"
    assert facts["cash_flow"]["transfer_amount"] == "500.00"
    assert facts["investment"]["net_inflow"] == "2000.00"
    assert facts["income_structure"]["categories"][0]["category"] == "Salary"
    assert facts["income_structure"]["categories"][0]["amount"] == "10000.00"
    assert facts["spending_structure"]["top_categories"][0]["category"] == "Housing"
    assert facts["spending_structure"]["fixed_expenses"][0]["category"] == "Housing"


def test_build_facts_returns_insufficient_data_for_empty_month():
    service = MonthlyReportFactsService()

    facts = service.build_facts(
        report_month="2026-04",
        current_transactions=[],
        previous_transactions=[],
        recent_average_transactions=[],
        current_balances={},
        previous_balances={},
    )

    assert facts["anomalies"][0]["message"] == "无法判断"
    assert facts["investment"]["return"] == "0.00"
    assert facts["income_structure"]["categories"] == []


def test_build_facts_returns_previous_month_income_and_expense_with_beancount_signs():
    service = MonthlyReportFactsService()

    current_income = build_transaction(
        date(2026, 4, 1),
        "工资",
        [
            Posting(account="Assets:Bank", amount=Decimal("8000"), currency="CNY"),
            Posting(account="Income:Salary", amount=Decimal("-8000"), currency="CNY"),
        ],
    )
    current_income_reversal = build_transaction(
        date(2026, 4, 2),
        "退款冲回",
        [
            Posting(account="Assets:Bank", amount=Decimal("-500"), currency="CNY"),
            Posting(account="Income:Salary", amount=Decimal("500"), currency="CNY"),
        ],
    )
    current_expense = build_transaction(
        date(2026, 4, 3),
        "餐饮",
        [
            Posting(account="Expenses:Food", amount=Decimal("1000"), currency="CNY"),
            Posting(account="Assets:Bank", amount=Decimal("-1000"), currency="CNY"),
        ],
    )
    current_expense_refund = build_transaction(
        date(2026, 4, 4),
        "餐饮退款",
        [
            Posting(account="Expenses:Food", amount=Decimal("-200"), currency="CNY"),
            Posting(account="Assets:Bank", amount=Decimal("200"), currency="CNY"),
        ],
    )

    previous_income = build_transaction(
        date(2026, 3, 1),
        "工资",
        [
            Posting(account="Assets:Bank", amount=Decimal("9000"), currency="CNY"),
            Posting(account="Income:Salary", amount=Decimal("-9000"), currency="CNY"),
        ],
    )
    previous_expense = build_transaction(
        date(2026, 3, 2),
        "餐饮",
        [
            Posting(account="Expenses:Food", amount=Decimal("600"), currency="CNY"),
            Posting(account="Assets:Bank", amount=Decimal("-600"), currency="CNY"),
        ],
    )

    facts = service.build_facts(
        report_month="2026-04",
        current_transactions=[
            current_income,
            current_income_reversal,
            current_expense,
            current_expense_refund,
        ],
        previous_transactions=[previous_income, previous_expense],
        recent_average_transactions=[],
        current_balances={},
        previous_balances={},
    )

    assert facts["summary_metrics"]["income"] == "7500.00"
    assert facts["summary_metrics"]["expense"] == "800.00"
    assert facts["change_analysis"]["previous_month"]["income"] == "9000.00"
    assert facts["change_analysis"]["previous_month"]["expense"] == "600.00"
    assert facts["change_analysis"]["drivers"][0]["category"] == "Food"
    assert facts["change_analysis"]["drivers"][0]["change_amount"] == "200.00"
