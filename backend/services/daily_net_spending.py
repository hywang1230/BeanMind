"""报表指定月份每日收支（收入为正、支出为负，不含转账）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.services.currency_convert import convert_currency_totals
from backend.services.ledger_aggregation import (
    LedgerAggregationService,
    month_range,
    normalize_decimal,
)


class DailyNetSpendingService:
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

    def default_month(self) -> str:
        now = datetime.now(ZoneInfo(self.timezone))
        return f"{now.year:04d}-{now.month:02d}"

    def get(self, month: str | None = None) -> dict:
        target_month = month or self.default_month()
        # validate format via month_range
        month_range(target_month)
        by_day = self.aggregation.daily_cashflow_by_currency(target_month)
        operating = self.beancount_service.get_operating_currency()

        days: list[dict] = []
        missing_exchange_rates: list[dict] = []

        for day_key in sorted(by_day.keys()):
            flows = by_day[day_key]
            income_map: dict[str, Decimal] = flows["income"]  # type: ignore[assignment]
            expense_map: dict[str, Decimal] = flows["expense"]  # type: ignore[assignment]
            has_activity = bool(flows["has_activity"])

            if has_activity and (income_map or expense_map):
                day_date = date.fromisoformat(day_key)
                rates = self.beancount_service.get_all_exchange_rates(
                    to_currency=operating, as_of_date=day_date
                )
                income, income_missing = convert_currency_totals(
                    income_map,
                    operating_currency=operating,
                    rates=rates,
                )
                expense, expense_missing = convert_currency_totals(
                    expense_map,
                    operating_currency=operating,
                    rates=rates,
                )
                missing = sorted(set(income_missing + expense_missing))
                if missing:
                    missing_exchange_rates.append(
                        {"date": day_key, "currencies": missing}
                    )
            else:
                income = Decimal("0")
                expense = Decimal("0")

            # 业务口径：收入为正、支出为负；net_spending = income + expense
            signed_expense = -expense
            days.append(
                {
                    "date": day_key,
                    "income": normalize_decimal(income),
                    "expense": normalize_decimal(signed_expense),
                    "net_spending": normalize_decimal(income + signed_expense),
                    "has_activity": has_activity,
                }
            )

        return {
            "month": target_month,
            "currency": operating,
            "days": days,
            "missing_exchange_rates": missing_exchange_rates,
        }
