"""单机月度分类预算服务。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session, selectinload

from backend.infrastructure.persistence.db.models import MonthlyBudget, MonthlyBudgetItem
from backend.services.currency_convert import convert_currency_totals
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
    def __init__(self, db: Session, aggregation: LedgerAggregationService, beancount_service) -> None:
        self.db = db
        self.aggregation = aggregation
        self.beancount_service = beancount_service

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

    def _pattern_totals(self, month: str, account_pattern: str) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        for pattern in self.parse_patterns(account_pattern):
            for currency, amount in self.aggregation.monthly_pattern_totals(month, pattern).items():
                totals[currency] = totals.get(currency, Decimal("0")) + amount
        return totals

    def _find(self, month: str) -> MonthlyBudget | None:
        month_range(month)
        return (
            self.db.query(MonthlyBudget)
            .options(selectinload(MonthlyBudget.items))
            .filter(MonthlyBudget.month == month)
            .first()
        )

    def _calculate_spending(
        self,
        month: str,
        account_patterns: list[str],
    ) -> tuple[str, dict[str, Decimal]]:
        _, month_end = month_range(month)
        operating_currency = self.beancount_service.get_operating_currency()
        rates = self.beancount_service.get_all_exchange_rates(
            to_currency=operating_currency,
            as_of_date=month_end,
        )
        spent_by_pattern: dict[str, Decimal] = {}
        missing: set[str] = set()
        for account_pattern in account_patterns:
            spent, item_missing = convert_currency_totals(
                self._pattern_totals(month, account_pattern),
                operating_currency=operating_currency,
                rates=rates,
            )
            spent_by_pattern[account_pattern] = spent
            missing.update(item_missing)
        if missing:
            raise MonthlyBudgetError(
                "MISSING_EXCHANGE_RATE",
                f"缺少币种 {', '.join(sorted(missing))} 对 {operating_currency} 的可用汇率",
                {
                    "month": month,
                    "operating_currency": operating_currency,
                    "currencies": sorted(missing),
                },
            )
        return operating_currency, spent_by_pattern

    def save(self, month: str, items: list[dict]) -> dict:
        self.aggregation.projection.assert_ready()
        month_range(month)
        normalized = self.validate_items(items)
        operating_currency, spent_by_pattern = self._calculate_spending(
            month,
            [item["account_pattern"] for item in normalized],
        )
        try:
            budget = self._find(month)
            if budget is None:
                budget = MonthlyBudget(month=month)
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
            self.db.refresh(budget)
        except Exception:
            self.db.rollback()
            raise
        return self._serialize(budget, operating_currency, spent_by_pattern)

    def get(self, month: str) -> dict:
        self.aggregation.projection.assert_ready()
        budget = self._find(month)
        operating_currency = self.beancount_service.get_operating_currency()
        if budget is None:
            return {"month": month, "currency": operating_currency, "total": "0", "items": []}
        operating_currency, spent_by_pattern = self._calculate_spending(
            month,
            [item.account_pattern for item in budget.items],
        )
        return self._serialize(budget, operating_currency, spent_by_pattern)

    def _serialize(
        self,
        budget: MonthlyBudget,
        operating_currency: str,
        spent_by_pattern: dict[str, Decimal],
    ) -> dict:
        output_items = []
        total_budget = Decimal("0")
        total_spent = Decimal("0")
        for item in budget.items:
            amount = Decimal(item.amount_text)
            spent = spent_by_pattern[item.account_pattern]
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
            "currency": operating_currency,
            "total": normalize_decimal(total_budget),
            "spent": normalize_decimal(total_spent),
            "remaining": normalize_decimal(total_budget - total_spent),
            "items": output_items,
        }

    def copy_previous(self, month: str, overwrite: bool = False) -> dict:
        start, _ = month_range(month)
        previous_month = f"{start.year - 1}-12" if start.month == 1 else f"{start.year}-{start.month - 1:02d}"
        if self._find(month) is not None and not overwrite:
            raise MonthlyBudgetError("MONTHLY_BUDGET_EXISTS", "目标月份已有预算")
        previous = self._find(previous_month)
        if previous is None:
            raise MonthlyBudgetError("PREVIOUS_MONTHLY_BUDGET_NOT_FOUND", "上月没有预算")
        return self.save(
            month,
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
