"""财务仪表盘 API。"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import get_beancount_service, get_db, settings
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionDirtyError
from backend.interfaces.errors import ApiError
from backend.services.dashboard import DashboardService
from backend.services.ledger_aggregation import LedgerAggregationService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(month: str | None = None, db: Session = Depends(get_db)):
    target = month or date.today().strftime("%Y-%m")
    try:
        return DashboardService(
            db,
            LedgerAggregationService(db, settings.LEDGER_FILE),
            get_beancount_service(),
            settings.LLM_ENABLED,
        ).get(target)
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, "INVALID_MONTH", str(exc)) from exc
