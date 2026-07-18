"""月度分类预算 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.config import get_beancount_service, get_db, settings
from backend.infrastructure.persistence.ledger_projection import LedgerProjectionDirtyError
from backend.interfaces.errors import ApiError
from backend.services.ledger_aggregation import LedgerAggregationService
from backend.services.monthly_budget import MonthlyBudgetError, MonthlyBudgetService


router = APIRouter(prefix="/api/budgets", tags=["budgets"])


class BudgetItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    account_pattern: str = Field(min_length=1, max_length=2000)
    amount: str
    display_order: int = 0


class MonthlyBudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BudgetItemInput]


def get_budget_service(db: Session = Depends(get_db)) -> MonthlyBudgetService:
    return MonthlyBudgetService(
        db,
        LedgerAggregationService(db, settings.LEDGER_FILE),
        get_beancount_service(),
    )


def map_budget_error(error: MonthlyBudgetError) -> ApiError:
    status_code = 400
    if error.code == "MONTHLY_BUDGET_EXISTS":
        status_code = 409
    elif error.code == "PREVIOUS_MONTHLY_BUDGET_NOT_FOUND":
        status_code = 404
    return ApiError(status_code, error.code, str(error), error.details)


@router.get("")
def get_monthly_budget(
    month: str,
    service: MonthlyBudgetService = Depends(get_budget_service),
):
    try:
        return service.get(month)
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except MonthlyBudgetError as exc:
        raise map_budget_error(exc) from exc
    except ValueError as exc:
        raise ApiError(400, "INVALID_MONTHLY_BUDGET", str(exc)) from exc


@router.put("/{month}")
def save_monthly_budget(
    month: str,
    request: MonthlyBudgetInput,
    service: MonthlyBudgetService = Depends(get_budget_service),
):
    try:
        return service.save(month, [item.model_dump() for item in request.items])
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except MonthlyBudgetError as exc:
        raise map_budget_error(exc) from exc
    except ValueError as exc:
        raise ApiError(400, "INVALID_MONTHLY_BUDGET", str(exc)) from exc


@router.post("/{month}/copy")
def copy_previous_budget(
    month: str,
    overwrite: bool = False,
    service: MonthlyBudgetService = Depends(get_budget_service),
):
    try:
        return service.copy_previous(month, overwrite)
    except LedgerProjectionDirtyError as exc:
        raise ApiError(503, exc.code, str(exc)) from exc
    except MonthlyBudgetError as exc:
        raise map_budget_error(exc) from exc
