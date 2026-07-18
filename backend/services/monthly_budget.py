"""单机月度分类预算服务。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session, selectinload

from backend.infrastructure.persistence.db.models import MonthlyBudget, MonthlyBudgetItem
from backend.services.currency_catalog import CurrencyCatalogError, CurrencyCatalogService
from backend.services.ledger_aggregation import (
    LedgerAggregationService,
    month_range,
    normalize_decimal,
)


class MonthlyBudgetError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details


class MonthlyBudgetService:
    def __init__(self, db: Session, aggregation: LedgerAggregationService) -> None:
        self.db = db
        self.aggregation = aggregation

    @staticmethod
    def parse_patterns(value: str) -> list[str]:
        """解析账户范围：支持英文/中文逗号分隔的多账户组合。"""
        patterns: list[str] = []
        for piece in str(value or "").replace("，", ",").split(","):
            pattern = piece.strip().strip(":")
            if pattern:
                patterns.append(pattern)
        return patterns

    @staticmethod
    def format_patterns(patterns: list[str]) -> str:
        return ",".join(patterns)

    @classmethod
    def validate_items(cls, items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, item in enumerate(items):
            patterns = cls.parse_patterns(str(item.get("account_pattern", "")))
            name = str(item.get("name", "")).strip()
            if not patterns or not name:
                raise MonthlyBudgetError("INVALID_MONTHLY_BUDGET", "分类名称和账户范围不能为空")
            try:
                amount = Decimal(str(item.get("amount")))
            except (InvalidOperation, TypeError) as exc:
                raise MonthlyBudgetError("INVALID_MONTHLY_BUDGET", "分类额度必须是 Decimal") from exc
            if not amount.is_finite() or amount < 0:
                raise MonthlyBudgetError("INVALID_MONTHLY_BUDGET", "分类额度必须大于等于零")

            # 同一分类内多 pattern 也不能重叠/重复
            for i, pattern in enumerate(patterns):
                for other in patterns[:i]:
                    if LedgerAggregationService.patterns_overlap(pattern, other):
                        raise MonthlyBudgetError(
                            "OVERLAPPING_BUDGET_PATTERN",
                            "预算账户范围不能重叠",
                            {"patterns": [other, pattern]},
                        )

            for existing in normalized:
                existing_patterns = cls.parse_patterns(existing["account_pattern"])
                for pattern in patterns:
                    for existing_pattern in existing_patterns:
                        if LedgerAggregationService.patterns_overlap(pattern, existing_pattern):
                            raise MonthlyBudgetError(
                                "OVERLAPPING_BUDGET_PATTERN",
                                "预算账户范围不能重叠",
                                {"patterns": [existing_pattern, pattern]},
                            )
            normalized.append(
                {
                    "name": name,
                    "account_pattern": cls.format_patterns(patterns),
                    "amount": amount,
                    "display_order": int(item.get("display_order", index)),
                }
            )
        return normalized

    def _pattern_spent(self, month: str, currency: str, account_pattern: str) -> Decimal:
        total = Decimal("0")
        for pattern in self.parse_patterns(account_pattern):
            total += self.aggregation.monthly_pattern_totals(month, pattern).get(currency, Decimal("0"))
        return total

    def _find(self, month: str, currency: str) -> MonthlyBudget | None:
        month_range(month)
        return (
            self.db.query(MonthlyBudget)
            .options(selectinload(MonthlyBudget.items))
            .filter(MonthlyBudget.month == month, MonthlyBudget.currency == currency)
            .first()
        )

    def _require_enabled_currency(self, currency: str) -> str:
        try:
            return CurrencyCatalogService(self.db).require_enabled(currency)
        except CurrencyCatalogError as exc:
            raise MonthlyBudgetError(exc.code, str(exc), exc.details) from exc

    def save(self, month: str, currency: str, items: list[dict]) -> dict:
        self.aggregation.projection.assert_ready()
        month_range(month)
        currency = currency.strip().upper()
        if not currency:
            raise MonthlyBudgetError("INVALID_MONTHLY_BUDGET", "币种不能为空")
        currency = self._require_enabled_currency(currency)
        normalized = self.validate_items(items)
        try:
            budget = self._find(month, currency)
            if budget is None:
                budget = MonthlyBudget(month=month, currency=currency)
                self.db.add(budget)
                self.db.flush()
            else:
                budget.items.clear()
                self.db.flush()
            for item in sorted(normalized, key=lambda value: value["display_order"]):
                budget.items.append(
                    MonthlyBudgetItem(
                        name=item["name"],
                        account_pattern=item["account_pattern"],
                        amount_text=normalize_decimal(item["amount"]),
                        display_order=item["display_order"],
                    )
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(month, currency)

    def get(self, month: str, currency: str) -> dict:
        self.aggregation.projection.assert_ready()
        budget = self._find(month, currency.upper())
        if budget is None:
            return {"month": month, "currency": currency.upper(), "total": "0", "items": []}
        output_items = []
        total_budget = Decimal("0")
        total_spent = Decimal("0")
        for item in budget.items:
            amount = Decimal(item.amount_text)
            spent = self._pattern_spent(month, budget.currency, item.account_pattern)
            remaining = amount - spent
            usage = None if amount == 0 else spent / amount
            if amount == 0 and spent > 0:
                risk = "EXCEEDED"
            elif usage is not None and usage >= 1:
                risk = "EXCEEDED"
            elif usage is not None and usage >= Decimal("0.8"):
                risk = "WARNING"
            else:
                risk = "NORMAL"
            total_budget += amount
            total_spent += spent
            output_items.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "account_pattern": item.account_pattern,
                    "amount": normalize_decimal(amount),
                    "spent": normalize_decimal(spent),
                    "remaining": normalize_decimal(remaining),
                    "usage_rate": normalize_decimal(usage) if usage is not None else None,
                    "risk": risk,
                    "display_order": item.display_order,
                }
            )
        return {
            "id": budget.id,
            "month": budget.month,
            "currency": budget.currency,
            "total": normalize_decimal(total_budget),
            "spent": normalize_decimal(total_spent),
            "remaining": normalize_decimal(total_budget - total_spent),
            "items": output_items,
        }

    def copy_previous(self, month: str, currency: str, overwrite: bool = False) -> dict:
        start, _ = month_range(month)
        previous_month = f"{start.year - 1}-12" if start.month == 1 else f"{start.year}-{start.month - 1:02d}"
        if self._find(month, currency) is not None and not overwrite:
            raise MonthlyBudgetError("MONTHLY_BUDGET_EXISTS", "目标月份已有预算")
        previous = self._find(previous_month, currency)
        if previous is None:
            raise MonthlyBudgetError("PREVIOUS_MONTHLY_BUDGET_NOT_FOUND", "上月没有预算")
        return self.save(
            month,
            currency,
            [
                {
                    "name": item.name,
                    "account_pattern": item.account_pattern,
                    "amount": item.amount_text,
                    "display_order": item.display_order,
                }
                for item in previous.items
            ],
        )
