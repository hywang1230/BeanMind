"""汇率 API 端点

提供汇率管理相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from backend.config import settings
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.repositories import ExchangeRateRepositoryImpl
from backend.application.services.exchange_rate_service import ExchangeRateApplicationService


# 创建路由
router = APIRouter(prefix="/api/exchange-rates", tags=["汇率管理"])


# ========== 请求模型 ==========

class CreateExchangeRateRequest(BaseModel):
    """创建汇率请求"""
    currency: str = Field(..., description="源货币代码（如 USD）", min_length=3, max_length=3)
    rate: str = Field(..., description="汇率")
    quote_currency: str = Field(default="CNY", description="目标货币（主货币）", min_length=3, max_length=3)
    effective_date: Optional[str] = Field(default=None, description="生效日期（ISO 格式，如 2025-01-01）")


class UpdateExchangeRateRequest(BaseModel):
    """更新汇率请求"""
    rate: str = Field(..., description="新汇率")


class ConvertAmountRequest(BaseModel):
    """货币换算请求"""
    amount: str = Field(..., description="金额")
    from_currency: str = Field(..., description="源货币")
    to_currency: str = Field(..., description="目标货币")
    as_of_date: Optional[str] = Field(default=None, description="截止日期（ISO 格式）")


# ========== 响应模型 ==========

class ExchangeRateResponse(BaseModel):
    """汇率响应"""
    currency: str = Field(..., description="源货币代码")
    rate: str = Field(..., description="汇率")
    quote_currency: str = Field(..., description="目标货币代码")
    effective_date: str = Field(..., description="生效日期")
    currency_pair: str = Field(..., description="货币对（如 USD/CNY）")


class ExchangeRateListResponse(BaseModel):
    """汇率列表响应"""
    exchange_rates: List[ExchangeRateResponse] = Field(..., description="汇率列表")
    total: int = Field(..., description="总数")


class CurrencyListResponse(BaseModel):
    """货币列表响应"""
    currencies: List[str] = Field(..., description="货币代码列表")
    total: int = Field(..., description="总数")


class ConvertAmountResponse(BaseModel):
    """货币换算响应"""
    original_amount: str = Field(..., description="原始金额")
    converted_amount: str = Field(..., description="换算后金额")
    from_currency: str = Field(..., description="源货币")
    to_currency: str = Field(..., description="目标货币")


class MessageResponse(BaseModel):
    """消息响应"""
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str


# ========== 依赖注入 ==========

def get_exchange_rate_service() -> ExchangeRateApplicationService:
    """
    获取汇率应用服务
    
    依赖注入工厂函数。
    """
    beancount_service = BeancountServiceProvider.get_service(settings.LEDGER_FILE)
    exchange_rate_repo = ExchangeRateRepositoryImpl(beancount_service)
    return ExchangeRateApplicationService(exchange_rate_repo)


# ========== API 端点 ==========

@router.post(
    "",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建汇率",
    description="创建新的汇率记录",
    responses={
        201: {"description": "创建成功", "model": ExchangeRateResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
def create_exchange_rate(
    request: CreateExchangeRateRequest,
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    创建汇率
    
    Beancount 格式: 2025-01-01 price USD 7.13 CNY
    表示 1 USD = 7.13 CNY
    """
    try:
        exchange_rate = exchange_rate_service.create_exchange_rate(
            currency=request.currency.upper(),
            rate=request.rate,
            quote_currency=request.quote_currency.upper(),
            effective_date=request.effective_date
        )
        return exchange_rate
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "",
    response_model=ExchangeRateListResponse,
    summary="获取汇率列表",
    description="获取所有货币对主货币的最新汇率",
    responses={
        200: {"description": "获取成功", "model": ExchangeRateListResponse},
    }
)
def list_exchange_rates(
    quote_currency: str = Query(default="CNY", description="目标货币（主货币）"),
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    获取汇率列表
    
    返回所有货币对主货币的最新汇率。
    """
    exchange_rates = exchange_rate_service.get_all_exchange_rates(quote_currency)
    return {
        "exchange_rates": exchange_rates,
        "total": len(exchange_rates)
    }


@router.get(
    "/currencies/common",
    response_model=CurrencyListResponse,
    summary="获取常用货币",
    description="获取常用货币代码列表",
    responses={
        200: {"description": "获取成功", "model": CurrencyListResponse},
    }
)
def get_common_currencies(
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    获取常用货币代码列表
    """
    currencies = exchange_rate_service.get_common_currencies()
    return {
        "currencies": currencies,
        "total": len(currencies)
    }


@router.get(
    "/currencies/available",
    response_model=CurrencyListResponse,
    summary="获取已定义货币",
    description="获取所有已定义汇率的货币代码",
    responses={
        200: {"description": "获取成功", "model": CurrencyListResponse},
    }
)
def get_available_currencies(
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    获取所有已定义汇率的货币代码
    """
    currencies = exchange_rate_service.get_available_currencies()
    return {
        "currencies": currencies,
        "total": len(currencies)
    }


@router.post(
    "/convert",
    response_model=ConvertAmountResponse,
    summary="货币换算",
    description="将金额从一种货币换算到另一种货币",
    responses={
        200: {"description": "换算成功", "model": ConvertAmountResponse},
        400: {"description": "无法换算（找不到汇率）", "model": ErrorResponse},
    }
)
def convert_amount(
    request: ConvertAmountRequest,
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    货币换算
    
    使用最新的汇率进行货币换算。
    """
    result = exchange_rate_service.convert_amount(
        amount=request.amount,
        from_currency=request.from_currency,
        to_currency=request.to_currency,
        as_of_date=request.as_of_date
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到 {request.from_currency} 到 {request.to_currency} 的汇率"
        )
    
    return {
        "original_amount": request.amount,
        "converted_amount": result,
        "from_currency": request.from_currency.upper(),
        "to_currency": request.to_currency.upper()
    }


@router.get(
    "/{currency}/history",
    response_model=ExchangeRateListResponse,
    summary="获取汇率历史",
    description="获取指定货币对的所有历史汇率",
    responses={
        200: {"description": "获取成功", "model": ExchangeRateListResponse},
    }
)
def get_exchange_rate_history(
    currency: str,
    quote_currency: str = Query(default="CNY", description="目标货币"),
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    获取汇率历史
    
    返回指定货币对的所有历史汇率记录，按日期降序排列。
    """
    exchange_rates = exchange_rate_service.get_exchange_rate_history(
        currency=currency.upper(),
        quote_currency=quote_currency.upper()
    )
    return {
        "exchange_rates": exchange_rates,
        "total": len(exchange_rates)
    }


@router.get(
    "/{currency}",
    response_model=ExchangeRateResponse,
    summary="获取最新汇率",
    description="获取指定货币的最新汇率",
    responses={
        200: {"description": "获取成功", "model": ExchangeRateResponse},
        404: {"description": "汇率不存在", "model": ErrorResponse},
    }
)
def get_exchange_rate(
    currency: str,
    quote_currency: str = Query(default="CNY", description="目标货币"),
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    获取最新汇率
    
    返回指定货币对主货币的最新汇率。
    """
    exchange_rate = exchange_rate_service.get_exchange_rate(
        currency=currency.upper(),
        quote_currency=quote_currency.upper()
    )
    
    if not exchange_rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"汇率 {currency.upper()}/{quote_currency.upper()} 不存在"
        )
    
    return exchange_rate


@router.put(
    "/{currency}/{effective_date}",
    response_model=ExchangeRateResponse,
    summary="更新汇率",
    description="更新指定日期的汇率",
    responses={
        200: {"description": "更新成功", "model": ExchangeRateResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "汇率不存在", "model": ErrorResponse},
    }
)
def update_exchange_rate(
    currency: str,
    effective_date: str,
    request: UpdateExchangeRateRequest,
    quote_currency: str = Query(default="CNY", description="目标货币"),
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    更新汇率
    
    更新指定日期的汇率记录。
    """
    try:
        exchange_rate = exchange_rate_service.update_exchange_rate(
            currency=currency.upper(),
            effective_date=effective_date,
            new_rate=request.rate,
            quote_currency=quote_currency.upper()
        )
        return exchange_rate
    except ValueError as e:
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )


@router.delete(
    "/{currency}/{effective_date}",
    response_model=MessageResponse,
    summary="删除汇率",
    description="删除指定日期的汇率记录",
    responses={
        200: {"description": "删除成功", "model": MessageResponse},
        404: {"description": "汇率不存在", "model": ErrorResponse},
    }
)
def delete_exchange_rate(
    currency: str,
    effective_date: str,
    quote_currency: str = Query(default="CNY", description="目标货币"),
    exchange_rate_service: ExchangeRateApplicationService = Depends(get_exchange_rate_service)
):
    """
    删除汇率
    
    删除指定日期的汇率记录。
    """
    result = exchange_rate_service.delete_exchange_rate(
        currency=currency.upper(),
        effective_date=effective_date,
        quote_currency=quote_currency.upper()
    )
    
    if result:
        return {"message": f"汇率 {currency.upper()}/{quote_currency.upper()} ({effective_date}) 已成功删除"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"汇率 {currency.upper()}/{quote_currency.upper()} ({effective_date}) 不存在"
        )
