"""报表近 12 个月收支趋势。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.services.currency_convert import convert_currency_totals
from backend.services.ledger_aggregation import (
    LedgerAggregationService,
    month_range,
    normalize_decimal,
    shift_month,
)


class MonthlyCashflowTrendService:
    WINDOW_MONTHS = 12

    def __init__(
        self,
        db: Session,
        aggregation: LedgerAggregationService,
        beancount_service,
        timezone: str = "Asia/Shanghai",
    ):
        self.db = db
        self.aggregation = aggregation
        self.beancount_service = beancount_service
        self.timezone = timezone

    def default_end_month(self) -> str:
        now = datetime.now(ZoneInfo(self.timezone))
        return f"{now.year:04d}-{now.month:02d}"

    def get(self, end_month: str | None = None) -> dict:
        target_end = end_month or self.default_end_month()
        # validate format via month_range
        month_range(target_end)
        start_month = shift_month(target_end, -(self.WINDOW_MONTHS - 1))
        by_month = self.aggregation.monthly_cashflow_by_currency(start_month, target_end)
        operating = self.beancount_service.get_operating_currency()

        points: list[dict[str, str]] = []
        missing_exchange_rates: list[dict] = []

        for month, flows in by_month.items():
            _, month_end = month_range(month)
            rates = self.beancount_service.get_all_exchange_rates(
                to_currency=operating, as_of_date=month_end
            )
            income, income_missing = convert_currency_totals(
                flows["income"],
                operating_currency=operating,
                rates=rates,
            )
            expense, expense_missing = convert_currency_totals(
                flows["expense"],
                operating_currency=operating,
                rates=rates,
            )
            missing = sorted(set(income_missing + expense_missing))
            if missing:
                missing_exchange_rates.append({"month": month, "currencies": missing})
            points.append(
                {
                    "month": month,
                    "income": normalize_decimal(income),
                    "expense": normalize_decimal(expense),
                    "net_income": normalize_decimal(income - expense),
                }
            )

        return {
            "start_month": start_month,
            "end_month": target_end,
            "currency": operating,
            "points": points,
            "missing_exchange_rates": missing_exchange_rates,
        }
