"""月报仓储"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models.monthly_report import MonthlyReport


class MonthlyReportRepository:
    """月报持久化仓储"""

    def __init__(self, session: Session):
        self._session = session

    def get_by_month(self, report_month: str, user_id: str = "default") -> Optional[MonthlyReport]:
        return (
            self._session.query(MonthlyReport)
            .filter_by(report_month=report_month, user_id=user_id)
            .first()
        )

    def list_reports(self, user_id: str = "default", limit: int = 12) -> List[MonthlyReport]:
        return (
            self._session.query(MonthlyReport)
            .filter_by(user_id=user_id)
            .order_by(MonthlyReport.report_month.desc())
            .limit(limit)
            .all()
        )

    def upsert(
        self,
        report_month: str,
        report_payload: Dict[str, Any],
        facts_payload: Dict[str, Any],
        model_provider: Optional[str],
        model_name: Optional[str],
        user_id: str = "default",
        status: str = "READY",
    ) -> MonthlyReport:
        monthly_report = self.get_by_month(report_month, user_id=user_id)
        if monthly_report is None:
            monthly_report = MonthlyReport(
                user_id=user_id,
                report_month=report_month,
            )
            self._session.add(monthly_report)

        monthly_report.status = status
        monthly_report.model_provider = model_provider
        monthly_report.model_name = model_name
        monthly_report.summary_text = report_payload.get("monthly_summary", "")
        monthly_report.report_json = json.dumps(report_payload, ensure_ascii=False)
        monthly_report.facts_json = json.dumps(facts_payload, ensure_ascii=False)

        self._session.commit()
        self._session.refresh(monthly_report)
        return monthly_report

    def mark_processing(
        self,
        report_month: str,
        model_provider: Optional[str],
        model_name: Optional[str],
        user_id: str = "default",
    ) -> MonthlyReport:
        monthly_report = self.get_by_month(report_month, user_id=user_id)
        if monthly_report is None:
            monthly_report = MonthlyReport(
                user_id=user_id,
                report_month=report_month,
            )
            self._session.add(monthly_report)

        monthly_report.status = "PROCESSING"
        monthly_report.model_provider = model_provider
        monthly_report.model_name = model_name
        self._session.commit()
        self._session.refresh(monthly_report)
        return monthly_report

    def mark_failed(
        self,
        report_month: str,
        model_provider: Optional[str],
        model_name: Optional[str],
        user_id: str = "default",
        message: str = "",
    ) -> MonthlyReport:
        monthly_report = self.get_by_month(report_month, user_id=user_id)
        if monthly_report is None:
            monthly_report = MonthlyReport(
                user_id=user_id,
                report_month=report_month,
            )
            self._session.add(monthly_report)

        monthly_report.status = "FAILED"
        monthly_report.model_provider = model_provider
        monthly_report.model_name = model_name
        if message:
            monthly_report.summary_text = message
        self._session.commit()
        self._session.refresh(monthly_report)
        return monthly_report

    @staticmethod
    def deserialize_json(raw_value: str) -> Dict[str, Any]:
        if not raw_value:
            return {}
        return json.loads(raw_value)
