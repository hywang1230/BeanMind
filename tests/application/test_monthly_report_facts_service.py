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
