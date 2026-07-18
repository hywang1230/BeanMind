"""首页确定性聚合。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models import MonthlyReview
from backend.services.currency_convert import convert_currency_totals
from backend.services.ledger_aggregation import LedgerAggregationService, month_range, normalize_decimal
from backend.services.monthly_budget import MonthlyBudgetService


class DashboardService:
    def __init__(self, db: Session, aggregation: LedgerAggregationService, beancount_service, llm_enabled: bool):
        self.db = db
        self.aggregation = aggregation
        self.beancount_service = beancount_service
        self.llm_enabled = llm_enabled

    def _convert(self, values: dict[str, Decimal], as_of: date) -> tuple[Decimal, list[str]]:
        operating = self.beancount_service.get_operating_currency()
        rates = self.beancount_service.get_all_exchange_rates(
            to_currency=operating, as_of_date=as_of
        )
        return convert_currency_totals(
            values,
            operating_currency=operating,
            rates=rates,
        )

    def get(self, month: str) -> dict:
        _, end = month_range(month)
        flows = self.aggregation.monthly_flows(month)
        income, income_missing = self._convert(flows["income"], end)
        expense, expense_missing = self._convert(flows["expense"], end)
        assets, asset_missing = self._convert(self.aggregation.balances(month, "Assets"), end)
        liability_signed, liability_missing = self._convert(
            self.aggregation.balances(month, "Liabilities"), end
        )
        liabilities = -liability_signed
        operating = self.beancount_service.get_operating_currency()
        budget = MonthlyBudgetService(self.db, self.aggregation).get(month, operating)
        risk_order = {"NORMAL": 0, "WARNING": 1, "EXCEEDED": 2}
        budget_risk = max(
            (item["risk"] for item in budget["items"]),
            key=lambda value: risk_order[value],
            default="NORMAL",
        )
        review = (
            self.db.query(MonthlyReview).filter(MonthlyReview.report_month == month).first()
        )
        review_status = review.generation_status if review else ("NOT_GENERATED" if self.llm_enabled else "DISABLED")
        return {
            "month": month,
            "currency": operating,
            "income": normalize_decimal(income),
            "expense": normalize_decimal(expense),
            "net_income": normalize_decimal(income - expense),
            "assets": normalize_decimal(assets),
            "liabilities": normalize_decimal(liabilities),
            "net_worth": normalize_decimal(assets - liabilities),
            "budget_risk": budget_risk,
            "review_status": review_status,
            "missing_exchange_rates": sorted(
                set(income_missing + expense_missing + asset_missing + liability_missing)
            ),
        }
