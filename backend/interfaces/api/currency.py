"""币种目录 API。"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_db, get_beancount_service
from backend.interfaces.errors import ApiError
from backend.services.currency_catalog import CurrencyCatalogError, CurrencyCatalogService


router = APIRouter(prefix="/api/currencies", tags=["currencies"])


class CreateCurrencyRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=3)
    name: str = Field(..., min_length=1, max_length=64)
    symbol: Optional[str] = Field(default=None, max_length=16)
    enabled: bool = True
    sort_order: Optional[int] = None


class UpdateCurrencyRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    symbol: Optional[str] = Field(default=None, max_length=16)
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


def get_currency_catalog_service(db: Session = Depends(get_db)) -> CurrencyCatalogService:
    beancount = None
    try:
        beancount = get_beancount_service()
        operating = beancount.get_operating_currency()
    except Exception:
        beancount = None
        operating = "CNY"
    service = CurrencyCatalogService(
        db,
        operating_currency=operating or "CNY",
        beancount_service=beancount,
    )
    service.ensure_seeded()
    return service


def map_currency_error(error: CurrencyCatalogError) -> ApiError:
    status_code = 400
    if error.code == "CURRENCY_NOT_FOUND":
        status_code = 404
    elif error.code == "CURRENCY_ALREADY_EXISTS":
        status_code = 409
    elif error.code in {
        "CANNOT_DISABLE_OPERATING_CURRENCY",
        "CANNOT_DELETE_OPERATING_CURRENCY",
        "CURRENCY_IN_USE",
    }:
        status_code = 400
    return ApiError(status_code, error.code, str(error), error.details)


@router.get("")
def list_currencies(
    enabled_only: Annotated[bool, Query()] = False,
    service: CurrencyCatalogService = Depends(get_currency_catalog_service),
):
    try:
        items = service.list_currencies(enabled_only=enabled_only)
        return {"currencies": items, "total": len(items)}
    except CurrencyCatalogError as exc:
        raise map_currency_error(exc) from exc


@router.post("", status_code=201)
def create_currency(
    request: CreateCurrencyRequest,
    service: CurrencyCatalogService = Depends(get_currency_catalog_service),
):
    try:
        return service.create(
            request.code,
            request.name,
            request.symbol,
            enabled=request.enabled,
            sort_order=request.sort_order,
        )
    except CurrencyCatalogError as exc:
        raise map_currency_error(exc) from exc


@router.patch("/{code}")
def update_currency(
    code: str,
    request: UpdateCurrencyRequest,
    service: CurrencyCatalogService = Depends(get_currency_catalog_service),
):
    try:
        return service.update(
            code,
            name=request.name,
            symbol=request.symbol,
            enabled=request.enabled,
            sort_order=request.sort_order,
        )
    except CurrencyCatalogError as exc:
        raise map_currency_error(exc) from exc


@router.delete("/{code}", status_code=204)
def delete_currency(
    code: str,
    service: CurrencyCatalogService = Depends(get_currency_catalog_service),
):
    try:
        service.delete(code)
        return Response(status_code=204)
    except CurrencyCatalogError as exc:
        raise map_currency_error(exc) from exc
