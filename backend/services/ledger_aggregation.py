"""直接在可重建账本投影上执行财务聚合。"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models import LedgerPosting, LedgerTransaction
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionService


def month_range(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-", 1)
        year, number = int(year_text), int(month_text)
        if number < 1 or number > 12:
            raise ValueError("月份必须使用 YYYY-MM 格式")
        start = date(year, number, 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("月份必须使用 YYYY-MM 格式") from exc
    return start, date(year, number, calendar.monthrange(year, number)[1])


def shift_month(month: str, delta: int) -> str:
    start, _ = month_range(month)
    year = start.year
    number = start.month + delta
    while number < 1:
        number += 12
        year -= 1
    while number > 12:
        number -= 12
        year += 1
    return f"{year:04d}-{number:02d}"


def months_between(start_month: str, end_month: str) -> list[str]:
    start, _ = month_range(start_month)
    end, _ = month_range(end_month)
    if (start.year, start.month) > (end.year, end.month):
        raise ValueError("开始月份不能晚于结束月份")
    months: list[str] = []
    year, number = start.year, start.month
    while (year, number) <= (end.year, end.month):
        months.append(f"{year:04d}-{number:02d}")
        number += 1
        if number > 12:
            number = 1
            year += 1
    return months


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

    def monthly_category_currency_totals(
        self, month: str, root: str
    ) -> dict[str, dict[str, Decimal]]:
        """按二级分类 + 币种聚合指定月金额（SQL group by 账户/币种后折叠）。

        账户 ``Expenses:Food`` / ``Expenses:Food:Lunch`` 的二级分类均为 ``Food``。
        返回 {category: {currency: Decimal}}；金额保留投影分录原符号。
        """
        self.projection.assert_ready()
        start, end = month_range(month)
        rows = (
            self.db.query(
                LedgerPosting.account,
                LedgerPosting.currency,
                func.decimal_sum(LedgerPosting.amount_text),
            )
            .join(LedgerTransaction, LedgerTransaction.id == LedgerPosting.transaction_id)
            .filter(LedgerTransaction.date >= start)
            .filter(LedgerTransaction.date <= end)
            .filter(self._pattern_filter(root))
            .group_by(LedgerPosting.account, LedgerPosting.currency)
            .all()
        )
        result: dict[str, dict[str, Decimal]] = {}
        for account, currency, total in rows:
            parts = str(account).split(":")
            if len(parts) < 2:
                continue
            category = parts[1]
            amount = Decimal(str(total or 0))
            bucket = result.setdefault(category, {})
            bucket[currency] = bucket.get(currency, Decimal("0")) + amount
        return result

    def monthly_cashflow_by_currency(
        self, start_month: str, end_month: str
    ) -> dict[str, dict[str, dict[str, Decimal]]]:
        """一次 SQL 聚合 [start_month, end_month] 内按月/收支根/币种的流量。

        返回结构：
        {
          "YYYY-MM": {
            "income": {currency: Decimal},   # Income 分录合计的相反数
            "expense": {currency: Decimal},  # Expenses 保留原符号
          }
        }
        缺月会补齐为零币种字典。
        """
        self.projection.assert_ready()
        months = months_between(start_month, end_month)
        start, _ = month_range(start_month)
        _, end = month_range(end_month)

        month_expr = func.strftime("%Y-%m", LedgerTransaction.date)
        flow_type = case(
            (self._pattern_filter("Income"), "income"),
            (self._pattern_filter("Expenses"), "expense"),
            else_="other",
        )

        rows = (
            self.db.query(
                month_expr.label("month"),
                flow_type.label("flow_type"),
                LedgerPosting.currency,
                func.decimal_sum(LedgerPosting.amount_text),
            )
            .join(LedgerTransaction, LedgerTransaction.id == LedgerPosting.transaction_id)
            .filter(LedgerTransaction.date >= start)
            .filter(LedgerTransaction.date <= end)
            .filter(or_(self._pattern_filter("Income"), self._pattern_filter("Expenses")))
            .group_by(month_expr, flow_type, LedgerPosting.currency)
            .all()
        )

        result: dict[str, dict[str, dict[str, Decimal]]] = {
            month: {"income": {}, "expense": {}} for month in months
        }
        for month_key, flow, currency, total in rows:
            if month_key not in result or flow not in ("income", "expense"):
                continue
            amount = Decimal(str(total or 0))
            if flow == "income":
                amount = -amount
            bucket = result[month_key][flow]
            bucket[currency] = bucket.get(currency, Decimal("0")) + amount
        return result

    def frequent_items(
        self,
        *,
        item_type: str,
        start: date,
        end: date,
        limit: int = 3,
    ) -> list[dict[str, object]]:
        """按账户/分类统计近期使用频次，直接在投影表聚合。

        item_type:
        - expense: Expenses:*
        - income: Income:*
        - transfer / account: Assets:* 与 Liabilities:*
        """
        self.projection.assert_ready()
        if start > end:
            raise ValueError("开始日期不能晚于结束日期")
        if limit < 1:
            raise ValueError("limit 必须大于等于 1")

        query = (
            self.db.query(
                LedgerPosting.account,
                func.count().label("use_count"),
                func.max(LedgerTransaction.date).label("last_used"),
            )
            .join(LedgerTransaction, LedgerTransaction.id == LedgerPosting.transaction_id)
            .filter(LedgerTransaction.date >= start)
            .filter(LedgerTransaction.date <= end)
        )

        if item_type == "expense":
            query = query.filter(self._pattern_filter("Expenses"))
        elif item_type == "income":
            query = query.filter(self._pattern_filter("Income"))
        elif item_type in ("transfer", "account"):
            query = query.filter(
                or_(
                    self._pattern_filter("Assets"),
                    self._pattern_filter("Liabilities"),
                )
            )
        else:
            raise ValueError(f"不支持的常用项类型: {item_type}")

        rows = (
            query.group_by(LedgerPosting.account)
            .order_by(
                func.count().desc(),
                func.max(LedgerTransaction.date).desc(),
                LedgerPosting.account.asc(),
            )
            .limit(limit)
            .all()
        )

        result: list[dict[str, object]] = []
        for name, use_count, last_used in rows:
            if hasattr(last_used, "isoformat"):
                last_used_text = last_used.isoformat()
            else:
                last_used_text = str(last_used)
            result.append(
                {
                    "name": name,
                    "count": int(use_count or 0),
                    "last_used": last_used_text,
                }
            )
        return result
