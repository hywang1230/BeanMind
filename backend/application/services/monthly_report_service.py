"""月报应用服务"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from backend.domain.analysis.monthly_report_facts_service import MonthlyReportFactsService
from backend.domain.transaction.entities.posting import Posting
from backend.domain.transaction.entities.transaction import Transaction
from backend.infrastructure.intelligence.skills.monthly_report import (
    MonthlyReportAgent,
    MonthlyReportAgentError,
    MonthlyReportModelConfig,
)
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories.transaction_repository_impl import (
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.repositories.monthly_report_repository import (
    MonthlyReportRepository,
)


@dataclass(frozen=True)
class MonthlyReportGenerationResult:
    """月报生成结果"""

    report_month: str
    status: str
    report: Dict[str, Any]
    facts: Dict[str, Any]
    model_provider: Optional[str]
    model_name: Optional[str]


@dataclass(frozen=True)
class MonthlyReportQueueResult:
    """月报异步排队结果"""

    report: Dict[str, Any]
    queued: bool


class MonthlyReportApplicationService:
    """月报编排服务"""

    def __init__(
        self,
        report_repository: MonthlyReportRepository,
        transaction_repository: TransactionRepositoryImpl,
        beancount_service: BeancountService,
        facts_service: MonthlyReportFactsService,
        agent: MonthlyReportAgent,
        user_id: str = "default",
    ):
        self._report_repository = report_repository
        self._transaction_repository = transaction_repository
        self._beancount_service = beancount_service
        self._facts_service = facts_service
        self._agent = agent
        self._user_id = user_id

    def get_report(self, report_month: str) -> Optional[Dict[str, Any]]:
        record = self._report_repository.get_by_month(report_month, user_id=self._user_id)
        if record is None:
            return None
        return self._build_response(record)

    def list_reports(self, limit: int = 12) -> list[Dict[str, Any]]:
        return [
            self._build_response(record)
            for record in self._report_repository.list_reports(user_id=self._user_id, limit=limit)
        ]

    def generate_report(self, report_month: str, regenerate: bool = False) -> Dict[str, Any]:
        existing = self._report_repository.get_by_month(report_month, user_id=self._user_id)
        if existing is not None and not regenerate:
            return self._build_response(existing)

        return self._run_generation(report_month)

    def queue_report_generation(
        self,
        report_month: str,
        regenerate: bool = False,
    ) -> MonthlyReportQueueResult:
        existing = self._report_repository.get_by_month(report_month, user_id=self._user_id)
        if existing is not None:
            if existing.status == "PROCESSING":
                return MonthlyReportQueueResult(report=self._build_response(existing), queued=False)
            if existing.status == "READY" and not regenerate:
                return MonthlyReportQueueResult(report=self._build_response(existing), queued=False)

        record = self._report_repository.mark_processing(
            report_month=report_month,
            model_provider=self._agent.model_config.provider,
            model_name=self._agent.model_config.model,
            user_id=self._user_id,
        )
        return MonthlyReportQueueResult(report=self._build_response(record), queued=True)

    def process_queued_report(self, report_month: str) -> Dict[str, Any]:
        try:
            return self._run_generation(report_month)
        except MonthlyReportAgentError as exc:
            self._report_repository.mark_failed(
                report_month=report_month,
                model_provider=self._agent.model_config.provider,
                model_name=self._agent.model_config.model,
                user_id=self._user_id,
                message=str(exc),
            )
            raise
        except Exception as exc:
            self._report_repository.mark_failed(
                report_month=report_month,
                model_provider=self._agent.model_config.provider,
                model_name=self._agent.model_config.model,
                user_id=self._user_id,
                message=f"生成月报失败: {exc}",
            )
            raise RuntimeError(f"生成月报失败: {exc}") from exc

    def _run_generation(self, report_month: str) -> Dict[str, Any]:
        facts = self._prepare_facts(report_month)
        report_payload = self._agent.generate(facts)
        record = self._report_repository.upsert(
            report_month=report_month,
            report_payload=report_payload,
            facts_payload=facts,
            model_provider=self._agent.model_config.provider,
            model_name=self._agent.model_config.model,
            user_id=self._user_id,
            status="READY",
        )
        return self._build_response(record)

    def try_generate_report(self, report_month: str, regenerate: bool = False) -> Dict[str, Any]:
        try:
            return self.generate_report(report_month, regenerate=regenerate)
        except MonthlyReportAgentError:
            raise
        except Exception as exc:
            raise RuntimeError(f"生成月报失败: {exc}") from exc

    def _prepare_facts(self, report_month: str) -> Dict[str, Any]:
        window = MonthlyReportFactsService.parse_month(report_month)
        previous_month_end = window.start_date - timedelta(days=1)
        previous_month = previous_month_end.strftime("%Y-%m")
        previous_window = MonthlyReportFactsService.parse_month(previous_month)

        current_transactions = self._transaction_repository.find_by_date_range(
            window.start_date,
            window.end_date,
        )
        previous_transactions = self._transaction_repository.find_by_date_range(
            previous_window.start_date,
            previous_window.end_date,
        )
        current_transactions = self._normalize_transactions_to_operating_currency(
            current_transactions,
            as_of_date=window.end_date,
        )
        previous_transactions = self._normalize_transactions_to_operating_currency(
            previous_transactions,
            as_of_date=previous_window.end_date,
        )

        recent_average_transactions = []
        cursor_end = previous_month_end
        for _ in range(3):
            month_str = cursor_end.strftime("%Y-%m")
            historical_window = MonthlyReportFactsService.parse_month(month_str)
            recent_average_transactions.append(
                self._normalize_transactions_to_operating_currency(
                    self._transaction_repository.find_by_date_range(
                        historical_window.start_date,
                        historical_window.end_date,
                    ),
                    as_of_date=historical_window.end_date,
                )
            )
            cursor_end = historical_window.start_date - timedelta(days=1)

        current_balances = self._beancount_service.get_account_balances(as_of_date=window.end_date)
        previous_balances = self._beancount_service.get_account_balances(
            as_of_date=window.start_date - timedelta(days=1)
        )

        return self._facts_service.build_facts(
            report_month=report_month,
            current_transactions=current_transactions,
            previous_transactions=previous_transactions,
            recent_average_transactions=recent_average_transactions,
            current_balances=current_balances,
            previous_balances=previous_balances,
        )

    def _normalize_transactions_to_operating_currency(
        self,
        transactions: list[Transaction],
        as_of_date: date,
    ) -> list[Transaction]:
        operating_currency = self._beancount_service.get_operating_currency()
        exchange_rates = self._beancount_service.get_all_exchange_rates(
            to_currency=operating_currency,
            as_of_date=as_of_date,
        )

        normalized_transactions = []
        for transaction in transactions:
            normalized_postings = []
            for posting in transaction.postings:
                rate = exchange_rates.get(posting.currency, Decimal("1"))
                normalized_postings.append(
                    Posting(
                        account=posting.account,
                        amount=posting.amount * rate,
                        currency=operating_currency,
                        cost=posting.cost,
                        cost_currency=posting.cost_currency,
                        price=posting.price,
                        price_currency=posting.price_currency,
                        flag=posting.flag,
                        meta=dict(posting.meta),
                    )
                )

            normalized_transactions.append(
                Transaction(
                    date=transaction.date,
                    description=transaction.description,
                    payee=transaction.payee,
                    postings=normalized_postings,
                    flag=transaction.flag,
                    tags=set(transaction.tags),
                    links=set(transaction.links),
                    meta=dict(transaction.meta),
                    id=transaction.id,
                    created_at=transaction.created_at,
                    updated_at=transaction.updated_at,
                )
            )
        return normalized_transactions

    def _build_response(self, record) -> Dict[str, Any]:
        report_payload = MonthlyReportRepository.deserialize_json(record.report_json)
        facts_payload = MonthlyReportRepository.deserialize_json(record.facts_json)
        return {
            "id": record.id,
            "report_month": record.report_month,
            "status": record.status,
            "model_provider": record.model_provider,
            "model_name": record.model_name,
            "summary_text": record.summary_text,
            "report": report_payload,
            "facts": facts_payload,
            "generated_at": record.generated_at.isoformat() if record.generated_at else None,
        }
