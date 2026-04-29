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
    def __init__(self, balances):
        self._balances = balances

    def get_account_balances(self, as_of_date=None):
        return self._balances.get(as_of_date.isoformat(), {})


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
