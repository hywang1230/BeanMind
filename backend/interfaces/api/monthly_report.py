"""月度复盘 API。"""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai.llm_client import OpenAICompatibleClient
from backend.config import get_beancount_service, get_db, get_db_session, settings
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionDirtyError
from backend.interfaces.errors import ApiError
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetService
from backend.services.monthly_review import MonthlyReviewService


router = APIRouter(prefix="/api/monthly-reviews", tags=["monthly-reviews"])


class GenerateRequest(BaseModel):
    regenerate: bool = False


def build_service(db: Session) -> MonthlyReviewService:
    aggregation = LedgerAggregationService(db, settings.LEDGER_FILE)
    beancount_service = get_beancount_service()
    return MonthlyReviewService(
        db,
        aggregation,
        MonthlyBudgetService(db, aggregation, beancount_service),
        OpenAICompatibleClient(
            enabled=settings.LLM_ENABLED,
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        ),
        beancount_service.get_operating_currency(),
    )


def get_service(db: Session = Depends(get_db)) -> MonthlyReviewService:
    return build_service(db)


def run_generation(month: str) -> None:
    db = get_db_session()
    try:
        build_service(db).process(month)
    finally:
        db.close()


@router.get("/{month}")
def get_review(month: str, service: MonthlyReviewService = Depends(get_service)):
    try:
        return service.response(month)
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, "INVALID_MONTH", str(exc)) from exc


@router.post("/{month}", status_code=202)
def generate_review(
    month: str,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    service: MonthlyReviewService = Depends(get_service),
):
    try:
        response, queued = service.queue(month, request.regenerate)
        if queued:
            background_tasks.add_task(run_generation, month)
        return response
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, "INVALID_MONTH", str(exc)) from exc
