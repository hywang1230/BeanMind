"""月报 API"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.application.services.monthly_report_service import MonthlyReportApplicationService
from backend.config import get_beancount_service, get_db, get_db_session, settings
from backend.domain.analysis.monthly_report_facts_service import MonthlyReportFactsService
from backend.infrastructure.intelligence.skills.monthly_report import (
    MonthlyReportAgent,
    MonthlyReportAgentError,
    MonthlyReportModelConfig,
)
from backend.infrastructure.persistence.beancount.repositories.transaction_repository_impl import (
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.repositories.monthly_report_repository import (
    MonthlyReportRepository,
)
from backend.interfaces.dto.monthly_report import (
    GenerateMonthlyReportRequest,
    MonthlyReportListResponse,
    MonthlyReportResponse,
)


router = APIRouter(prefix="/api/monthly-reports", tags=["monthly-reports"])


def build_monthly_report_service(db: Session) -> MonthlyReportApplicationService:
    beancount_service = get_beancount_service()
    transaction_repository = TransactionRepositoryImpl(beancount_service, db)
    report_repository = MonthlyReportRepository(db)
    facts_service = MonthlyReportFactsService()
    agent = MonthlyReportAgent(
        MonthlyReportModelConfig(
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL_NAME,
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
        )
    )
    return MonthlyReportApplicationService(
        report_repository=report_repository,
        transaction_repository=transaction_repository,
        beancount_service=beancount_service,
        facts_service=facts_service,
        agent=agent,
    )


def get_monthly_report_service(db: Session = Depends(get_db)) -> MonthlyReportApplicationService:
    return build_monthly_report_service(db)


def run_monthly_report_generation(report_month: str) -> None:
    db = get_db_session()
    try:
        service = build_monthly_report_service(db)
        service.process_queued_report(report_month)
    finally:
        db.close()


@router.post(
    "/generate",
    response_model=MonthlyReportResponse,
    summary="生成或重生成月报",
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_monthly_report(
    request: GenerateMonthlyReportRequest,
    background_tasks: BackgroundTasks,
    service: MonthlyReportApplicationService = Depends(get_monthly_report_service),
):
    try:
        queue_result = service.queue_report_generation(
            request.report_month,
            regenerate=request.regenerate,
        )
        if queue_result.queued:
            background_tasks.add_task(run_monthly_report_generation, request.report_month)
        return queue_result.report
    except MonthlyReportAgentError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "",
    response_model=MonthlyReportListResponse,
    summary="获取月报列表",
)
def list_monthly_reports(
    limit: int = Query(12, ge=1, le=60),
    service: MonthlyReportApplicationService = Depends(get_monthly_report_service),
):
    reports = service.list_reports(limit=limit)
    return {"reports": reports, "total": len(reports)}


@router.get(
    "/{report_month}",
    response_model=MonthlyReportResponse,
    summary="获取指定月份月报",
)
def get_monthly_report(
    report_month: str,
    service: MonthlyReportApplicationService = Depends(get_monthly_report_service),
):
    report = service.get_report(report_month)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="月报不存在")
    return report
