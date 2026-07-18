"""月度复盘事实与生成状态。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.ai.llm_client import LlmUnavailableError, OpenAICompatibleClient
from backend.infrastructure.persistence.db.models import MonthlyReview
from backend.services.ledger_aggregation import LedgerAggregationService, month_range, normalize_decimal
from backend.services.monthly_budget import MonthlyBudgetService


def previous_month(month: str) -> str:
    start, _ = month_range(month)
    return f"{start.year - 1}-12" if start.month == 1 else f"{start.year}-{start.month - 1:02d}"


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

    def build_facts(self, month: str) -> dict:
        current = self.aggregation.monthly_flows(month)
        previous = self.aggregation.monthly_flows(previous_month(month))
        budget = self.budget_service.get(month)

        def encoded(flows: dict[str, dict[str, Decimal]]) -> dict:
            return {
                name: {currency: normalize_decimal(amount) for currency, amount in values.items()}
                for name, values in flows.items()
            }

        return {
            "month": month,
            "current": encoded(current),
            "previous": encoded(previous),
            "budget": budget,
            "risk_items": [
                {"name": item["name"], "risk": item["risk"]}
                for item in budget["items"]
                if item["risk"] != "NORMAL"
            ],
        }

    @staticmethod
    def _decode(value: str, fallback):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    def response(self, month: str) -> dict:
        record = self._record(month)
        if record is None:
            facts = self.build_facts(month)
            return {
                "report_month": month,
                "status": "DISABLED" if not self.client.enabled else "NOT_GENERATED",
                "facts": facts,
                "monthly_summary": "",
                "next_month_suggestions": [],
                "last_error": None,
                "generated_at": None,
            }
        facts = self._decode(record.facts_json, {}) or self._decode(record.pending_facts_json, {})
        return {
            "report_month": month,
            "status": "DISABLED" if not self.client.enabled else record.generation_status,
            "facts": facts,
            "monthly_summary": record.summary_text,
            "next_month_suggestions": self._decode(record.suggestions_json, []),
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
            record.suggestions_json = json.dumps(text.next_month_suggestions, ensure_ascii=False)
            record.generation_status = "READY"
            record.last_error = None
            record.last_success_at = datetime.now()
            self.db.commit()
        except LlmUnavailableError as exc:
            record.generation_status = "FAILED"
            record.last_error = str(exc)
            self.db.commit()
        return self.response(month)
