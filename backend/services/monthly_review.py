"""月度复盘事实与生成状态。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.ai.llm_client import LlmUnavailableError, OpenAICompatibleClient
from backend.infrastructure.persistence.db.models import MonthlyReview
from backend.services.currency_convert import convert_currency_totals
from backend.services.ledger_aggregation import LedgerAggregationService, month_range, normalize_decimal
from backend.services.monthly_budget import MonthlyBudgetService

TOP_CATEGORY_LIMIT = 5


def previous_month(month: str) -> str:
    start, _ = month_range(month)
    return f"{start.year - 1}-12" if start.month == 1 else f"{start.year}-{start.month - 1:02d}"


RATIO_QUANT = Decimal("0.0001")


def _format_ratio(value: Decimal | str | int) -> str:
    """比例/变化率保留 4 位小数，避免 LLM 与页面直接引用超长小数。"""
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("比例必须是有限 Decimal")
    return format(number.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP), "f")


def _change_rate(current: Decimal, previous: Decimal) -> str | None:
    if previous == 0:
        return None
    return _format_ratio(current / previous - 1)


class MonthlyReviewService:
    def __init__(
        self,
        db: Session,
        aggregation: LedgerAggregationService,
        budget_service: MonthlyBudgetService,
        client: OpenAICompatibleClient,
        operating_currency: str,
    ) -> None:
        self.db = db
        self.aggregation = aggregation
        self.budget_service = budget_service
        self.client = client
        self.operating_currency = operating_currency

    def _record(self, month: str) -> MonthlyReview | None:
        month_range(month)
        return self.db.query(MonthlyReview).filter(MonthlyReview.report_month == month).first()

    def _rates(self, as_of) -> dict:
        return self.budget_service.beancount_service.get_all_exchange_rates(
            to_currency=self.operating_currency,
            as_of_date=as_of,
        )

    def _convert_flows(
        self, flows: dict[str, dict[str, Decimal]], rates: dict
    ) -> tuple[dict[str, Decimal], list[str]]:
        income, income_missing = convert_currency_totals(
            flows["income"],
            operating_currency=self.operating_currency,
            rates=rates,
        )
        expense, expense_missing = convert_currency_totals(
            flows["expense"],
            operating_currency=self.operating_currency,
            rates=rates,
        )
        missing = sorted(set(income_missing + expense_missing))
        return {"income": income, "expense": expense, "net": income - expense}, missing

    def _encode_period(self, values: dict[str, Decimal]) -> dict[str, str]:
        return {
            "income": normalize_decimal(values["income"]),
            "expense": normalize_decimal(values["expense"]),
            "net": normalize_decimal(values["net"]),
        }

    def _top_categories(
        self,
        month: str,
        *,
        root: str,
        invert: bool,
        rates: dict,
        limit: int = TOP_CATEGORY_LIMIT,
    ) -> tuple[list[dict[str, str | None]], list[str]]:
        raw = self.aggregation.monthly_category_currency_totals(month, root)
        converted: list[tuple[str, Decimal]] = []
        missing: set[str] = set()
        for name, by_currency in raw.items():
            signed = {
                currency: (-amount if invert else amount)
                for currency, amount in by_currency.items()
            }
            total, item_missing = convert_currency_totals(
                signed,
                operating_currency=self.operating_currency,
                rates=rates,
            )
            missing.update(item_missing)
            if total == 0:
                continue
            converted.append((name, total))
        converted.sort(key=lambda item: item[1], reverse=True)
        top = converted[:limit]
        base = sum((amount for _, amount in converted), Decimal("0"))
        output: list[dict[str, str | None]] = []
        for name, amount in top:
            share = None if base == 0 else _format_ratio(amount / base)
            output.append(
                {
                    "name": name,
                    "amount": normalize_decimal(amount),
                    "share": share,
                }
            )
        return output, sorted(missing)

    def _budget_summary(self, month: str) -> tuple[dict, list[dict]]:
        budget = self.budget_service.get(month)
        items = budget.get("items") or []
        total = Decimal(str(budget.get("total") or "0"))
        spent = Decimal(str(budget.get("spent") or "0"))
        remaining = budget.get("remaining")
        if remaining is None:
            remaining_text = normalize_decimal(total - spent)
        else:
            remaining_text = str(remaining)
        usage_rate = None if total == 0 else _format_ratio(spent / total)
        risk_items = []
        slim_items = []
        for item in items:
            risk = item.get("risk") or "NORMAL"
            item_usage = item.get("usage_rate")
            slim = {
                "name": item["name"],
                "amount": item.get("amount"),
                "spent": item.get("spent"),
                "usage_rate": None if item_usage is None else _format_ratio(item_usage),
                "risk": risk,
            }
            if risk != "NORMAL":
                risk_items.append({"name": item["name"], "risk": risk})
                slim_items.append(slim)
        summary = {
            "currency": budget.get("currency") or self.operating_currency,
            "total": normalize_decimal(total),
            "spent": normalize_decimal(spent),
            "remaining": remaining_text,
            "usage_rate": usage_rate,
            "items": slim_items,
        }
        return summary, risk_items

    def build_facts(self, month: str) -> dict:
        prev = previous_month(month)
        _, current_end = month_range(month)
        _, previous_end = month_range(prev)
        current_rates = self._rates(current_end)
        previous_rates = self._rates(previous_end)

        current_values, current_missing = self._convert_flows(
            self.aggregation.monthly_flows(month), current_rates
        )
        previous_values, previous_missing = self._convert_flows(
            self.aggregation.monthly_flows(prev), previous_rates
        )
        top_expense, expense_cat_missing = self._top_categories(
            month, root="Expenses", invert=False, rates=current_rates
        )
        top_income, income_cat_missing = self._top_categories(
            month, root="Income", invert=True, rates=current_rates
        )
        budget_summary, risk_items = self._budget_summary(month)
        missing = sorted(
            set(
                current_missing
                + previous_missing
                + expense_cat_missing
                + income_cat_missing
            )
        )
        return {
            "month": month,
            "currency": self.operating_currency,
            "current": self._encode_period(current_values),
            "previous": self._encode_period(previous_values),
            "changes": {
                "income_delta": normalize_decimal(
                    current_values["income"] - previous_values["income"]
                ),
                "expense_delta": normalize_decimal(
                    current_values["expense"] - previous_values["expense"]
                ),
                "net_delta": normalize_decimal(
                    current_values["net"] - previous_values["net"]
                ),
                "income_change_rate": _change_rate(
                    current_values["income"], previous_values["income"]
                ),
                "expense_change_rate": _change_rate(
                    current_values["expense"], previous_values["expense"]
                ),
            },
            "budget": budget_summary,
            "risk_items": risk_items,
            "top_expense_categories": top_expense,
            "top_income_categories": top_income,
            "missing_exchange_rates": missing,
        }

    @staticmethod
    def _decode(value: str, fallback):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _decode_suggestions(value: str | None) -> tuple[list[str], list[str]]:
        try:
            decoded = json.loads(value) if value is not None else []
        except (TypeError, json.JSONDecodeError):
            return [], []
        if isinstance(decoded, list):
            return [], [str(item) for item in decoded]
        if isinstance(decoded, dict):
            highlights = decoded.get("highlights") or []
            suggestions = decoded.get("next_month_suggestions") or []
            if not isinstance(highlights, list):
                highlights = []
            if not isinstance(suggestions, list):
                suggestions = []
            return [str(item) for item in highlights], [str(item) for item in suggestions]
        return [], []

    def response(self, month: str) -> dict:
        record = self._record(month)
        if record is None:
            facts = self.build_facts(month)
            return {
                "report_month": month,
                "status": "DISABLED" if not self.client.enabled else "NOT_GENERATED",
                "facts": facts,
                "monthly_summary": "",
                "highlights": [],
                "next_month_suggestions": [],
                "last_error": None,
                "generated_at": None,
            }
        facts = self._decode(record.facts_json, {}) or self._decode(record.pending_facts_json, {})
        highlights, suggestions = self._decode_suggestions(record.suggestions_json)
        return {
            "report_month": month,
            "status": "DISABLED" if not self.client.enabled else record.generation_status,
            "facts": facts,
            "monthly_summary": record.summary_text,
            "highlights": highlights,
            "next_month_suggestions": suggestions,
            "last_error": record.last_error,
            "generated_at": record.last_success_at.isoformat() if record.last_success_at else None,
        }

    def queue(self, month: str, regenerate: bool = False) -> tuple[dict, bool]:
        if not self.client.enabled:
            return self.response(month), False
        record = self._record(month)
        if record is not None:
            if record.generation_status == "PROCESSING":
                return self.response(month), False
            if record.generation_status == "READY" and not regenerate:
                return self.response(month), False
        facts = self.build_facts(month)
        if record is None:
            record = MonthlyReview(report_month=month)
            self.db.add(record)
        record.generation_status = "PROCESSING"
        record.model_name = self.client.model
        record.pending_facts_json = json.dumps(facts, ensure_ascii=False)
        record.last_error = None
        record.requested_at = datetime.now()
        self.db.commit()
        return self.response(month), True

    def process(self, month: str) -> dict:
        record = self._record(month)
        if record is None:
            raise ValueError("月度复盘任务不存在")
        facts = self._decode(record.pending_facts_json, {})
        try:
            text = self.client.generate(facts)
            record.facts_json = record.pending_facts_json
            record.summary_text = text.monthly_summary
            record.suggestions_json = json.dumps(
                {
                    "highlights": text.highlights,
                    "next_month_suggestions": text.next_month_suggestions,
                },
                ensure_ascii=False,
            )
            record.generation_status = "READY"
            record.last_error = None
            record.last_success_at = datetime.now()
            self.db.commit()
        except LlmUnavailableError as exc:
            record.generation_status = "FAILED"
            record.last_error = str(exc)
            self.db.commit()
        return self.response(month)
