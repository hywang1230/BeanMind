"""直接在可重建账本投影上执行财务聚合。"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models import LedgerPosting, LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService


def month_range(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-", 1)
        year, number = int(year_text), int(month_text)
        start = date(year, number, 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("月份必须使用 YYYY-MM 格式") from exc
    return start, date(year, number, calendar.monthrange(year, number)[1])


def normalize_decimal(value: Decimal | str | int) -> str:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("金额必须是有限 Decimal")
    return format(number, "f")


def _escaped_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class _DecimalSum:
    """SQLite 自定义聚合，避免 NUMERIC affinity 转成二进制浮点。"""

    def __init__(self) -> None:
        self.total = Decimal("0")

    def step(self, value: str | None) -> None:
        if value is not None:
            self.total += Decimal(value)

    def finalize(self) -> str:
        return format(self.total, "f")


class LedgerAggregationService:
    def __init__(self, db: Session, ledger_path) -> None:
        self.db = db
        self.projection = LedgerProjectionService(db, ledger_path)
        raw_connection = db.connection().connection.driver_connection
        raw_connection.create_aggregate("decimal_sum", 1, _DecimalSum)

    @staticmethod
    def patterns_overlap(first: str, second: str) -> bool:
        return first == second or first.startswith(f"{second}:") or second.startswith(f"{first}:")

    @staticmethod
    def _pattern_filter(pattern: str):
        escaped = _escaped_like(pattern)
        return or_(
            LedgerPosting.account == pattern,
            LedgerPosting.account.like(f"{escaped}:%", escape="\\"),
        )

    def _totals(self, start: date | None, end: date, pattern: str) -> dict[str, Decimal]:
        self.projection.assert_ready()
        query = (
            self.db.query(LedgerPosting.currency, func.decimal_sum(LedgerPosting.amount_text))
            .join(LedgerTransaction, LedgerTransaction.id == LedgerPosting.transaction_id)
            .filter(LedgerTransaction.date <= end)
            .filter(self._pattern_filter(pattern))
        )
        if start is not None:
            query = query.filter(LedgerTransaction.date >= start)
        return {
            currency: Decimal(str(total or 0))
            for currency, total in query.group_by(LedgerPosting.currency).all()
        }

    def monthly_pattern_totals(self, month: str, pattern: str) -> dict[str, Decimal]:
        start, end = month_range(month)
        return self._totals(start, end, pattern)

    def balances(self, month: str, pattern: str) -> dict[str, Decimal]:
        _, end = month_range(month)
        return self._totals(None, end, pattern)

    def monthly_flows(self, month: str) -> dict[str, dict[str, Decimal]]:
        expenses = self.monthly_pattern_totals(month, "Expenses")
        raw_income = self.monthly_pattern_totals(month, "Income")
        return {
            "expense": expenses,
            "income": {currency: -amount for currency, amount in raw_income.items()},
        }
