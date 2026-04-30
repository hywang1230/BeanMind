from datetime import date
from decimal import Decimal

from backend.application.services.monthly_report_service import MonthlyReportApplicationService
from backend.domain.analysis.monthly_report_facts_service import MonthlyReportFactsService
from backend.domain.transaction.entities.posting import Posting
from backend.domain.transaction.entities.transaction import Transaction
from backend.infrastructure.persistence.db.models import Base
from backend.infrastructure.persistence.db.repositories.monthly_report_repository import (
    MonthlyReportRepository,
)
from backend.infrastructure.persistence.db.models.monthly_report import MonthlyReport

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeTransactionRepository:
    def __init__(self, transactions):
        self._transactions = transactions

    def find_by_date_range(self, start_date, end_date):
        return [txn for txn in self._transactions if start_date <= txn.date <= end_date]


class FakeBeancountService:
    def __init__(self, balances, operating_currency="CNY", exchange_rates=None):
        self._balances = balances
        self._operating_currency = operating_currency
        self._exchange_rates = exchange_rates or {}

    def get_account_balances(self, as_of_date=None):
        return self._balances.get(as_of_date.isoformat(), {})

    def get_operating_currency(self):
        return self._operating_currency

    def get_all_exchange_rates(self, to_currency="CNY", as_of_date=None):
        return self._exchange_rates.get(as_of_date.isoformat(), {to_currency: Decimal("1")})


class FakeAgent:
    class Config:
        provider = "fake"
        model = "fake-model"

    model_config = Config()

    def generate(self, facts):
        return {
            "monthly_summary": f"{facts['report_month']} summary",
            "core_metrics": facts["summary_metrics"],
            "spending_structure": facts["spending_structure"],
            "income_structure": facts["income_structure"],
            "change_analysis": facts["change_analysis"],
            "anomalies": facts["anomalies"],
            "cash_flow": facts["cash_flow"],
            "investment": facts["investment"],
            "next_month_suggestions": ["控制支出"],
        }


def build_transaction(txn_date: date, description: str, postings):
    return Transaction(date=txn_date, description=description, postings=postings)


def test_generate_report_persists_and_supports_regeneration():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    transactions = [
        build_transaction(
            date(2026, 4, 1),
            "工资",
            [
                Posting(account="Assets:Bank", amount=Decimal("5000"), currency="CNY"),
                Posting(account="Income:Salary", amount=Decimal("-5000"), currency="CNY"),
            ],
        ),
        build_transaction(
            date(2026, 4, 3),
            "吃饭",
            [
                Posting(account="Expenses:Food", amount=Decimal("200"), currency="CNY"),
                Posting(account="Assets:Bank", amount=Decimal("-200"), currency="CNY"),
            ],
        ),
    ]
    balance_map = {
        "2026-04-30": {"Assets:Bank": {"CNY": Decimal("4800")}},
        "2026-03-31": {"Assets:Bank": {"CNY": Decimal("0")}},
        "2026-02-28": {"Assets:Bank": {"CNY": Decimal("0")}},
        "2026-01-31": {"Assets:Bank": {"CNY": Decimal("0")}},
        "2025-12-31": {"Assets:Bank": {"CNY": Decimal("0")}},
    }

    service = MonthlyReportApplicationService(
        report_repository=MonthlyReportRepository(session),
        transaction_repository=FakeTransactionRepository(transactions),
        beancount_service=FakeBeancountService(balance_map),
        facts_service=MonthlyReportFactsService(),
        agent=FakeAgent(),
    )

    first = service.generate_report("2026-04")
    second = service.generate_report("2026-04", regenerate=True)

    assert first["report_month"] == "2026-04"
    assert second["summary_text"] == "2026-04 summary"
    assert session.query(MonthlyReport).count() == 1
    assert service.list_reports(limit=5)[0]["report_month"] == "2026-04"


def test_generate_report_normalizes_previous_month_transactions_to_operating_currency():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    transactions = [
        build_transaction(
            date(2026, 3, 10),
            "美元工资",
            [
                Posting(account="Assets:Bank", amount=Decimal("100"), currency="USD"),
                Posting(account="Income:Salary", amount=Decimal("-100"), currency="USD"),
            ],
        ),
        build_transaction(
            date(2026, 3, 12),
            "美元支出",
            [
                Posting(account="Expenses:Food", amount=Decimal("20"), currency="USD"),
                Posting(account="Assets:Bank", amount=Decimal("-20"), currency="USD"),
            ],
        ),
    ]
    balance_map = {
        "2026-04-30": {},
        "2026-03-31": {},
        "2026-02-28": {},
        "2026-01-31": {},
        "2025-12-31": {},
    }
    exchange_rates = {
        "2026-03-31": {"CNY": Decimal("1"), "USD": Decimal("7")},
        "2026-02-28": {"CNY": Decimal("1"), "USD": Decimal("7")},
        "2026-01-31": {"CNY": Decimal("1"), "USD": Decimal("7")},
        "2025-12-31": {"CNY": Decimal("1"), "USD": Decimal("7")},
        "2026-04-30": {"CNY": Decimal("1"), "USD": Decimal("7")},
    }

    service = MonthlyReportApplicationService(
        report_repository=MonthlyReportRepository(session),
        transaction_repository=FakeTransactionRepository(transactions),
        beancount_service=FakeBeancountService(balance_map, exchange_rates=exchange_rates),
        facts_service=MonthlyReportFactsService(),
        agent=FakeAgent(),
    )

    report = service.generate_report("2026-04")

    assert report["facts"]["change_analysis"]["previous_month"]["income"] == "700.00"
    assert report["facts"]["change_analysis"]["previous_month"]["expense"] == "140.00"
