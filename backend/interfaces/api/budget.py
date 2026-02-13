"""预算 API 端点

提供预算管理相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy.orm import Session

from backend.config import settings, get_db
from backend.infrastructure.persistence.db.repositories.budget_repository_impl import BudgetRepositoryImpl
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.repositories import TransactionRepositoryImpl
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.application.services import BudgetApplicationService
from backend.interfaces.dto.request.budget import (
    CreateBudgetRequest,
    UpdateBudgetRequest,
    AddBudgetItemRequest
)
from backend.interfaces.dto.response.budget import (
    BudgetResponse,
    BudgetListResponse,
    BudgetSummaryResponse,
    BudgetCycleResponse,
    BudgetCycleListResponse
)
from backend.interfaces.dto.response.auth import MessageResponse, ErrorResponse


# 创建路由
router = APIRouter(prefix="/api/budgets", tags=["预算管理"])

# 默认用户ID（单用户模式）
DEFAULT_USER_ID = "default"


def get_budget_service(db: Session = Depends(get_db)) -> BudgetApplicationService:
    """
    获取预算应用服务
    
    依赖注入工厂函数。
    """
    # 创建预算仓储
    budget_repo = BudgetRepositoryImpl(db)
    
    # 创建交易仓储（用于计算执行情况）- 使用共享的 Beancount 服务
    beancount_service = BeancountServiceProvider.get_service(settings.LEDGER_FILE)
    transaction_repo = TransactionRepositoryImpl(beancount_service, db)
    
    # 创建执行计算服务
    execution_service = BudgetExecutionService(transaction_repo)
    
    # 创建应用服务
    return BudgetApplicationService(budget_repo, execution_service)


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建预算",
    description="创建新的预算",
    responses={
        201: {"description": "创建成功", "model": BudgetResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
async def create_budget(
    request: CreateBudgetRequest,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    创建新预算
    
    需要提供预算名称、周期类型、日期范围等信息。
    """
    try:
        items = [item.model_dump() for item in request.items] if request.items else []
        
        budget_dto = await budget_service.create_budget(
            user_id=DEFAULT_USER_ID,
            name=request.name,
            amount=request.amount,
            period_type=request.period_type.value,
            start_date=request.start_date,
            end_date=request.end_date,
            items=items,
            cycle_type=request.cycle_type.value,
            carry_over_enabled=request.carry_over_enabled
        )
        return budget_dto
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "",
    response_model=BudgetListResponse,
    summary="获取预算列表",
    description="获取所有预算或按条件筛选",
    responses={
        200: {"description": "获取成功", "model": BudgetListResponse},
    }
)
async def list_budgets(
    is_active: Optional[bool] = Query(None, description="是否只获取活跃预算"),
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算列表
    
    支持按活跃状态筛选。
    """
    budgets = await budget_service.get_budgets_by_user(DEFAULT_USER_ID, is_active)
    return {
        "budgets": budgets,
        "total": len(budgets)
    }


@router.get(
    "/summary",
    response_model=BudgetSummaryResponse,
    summary="获取预算概览",
    description="获取预算统计概览信息",
    responses={
        200: {"description": "获取成功", "model": BudgetSummaryResponse},
    }
)
async def get_budget_summary(
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算概览统计
    
    包含总预算、总支出、执行率等信息。
    """
    return await budget_service.get_budget_summary(DEFAULT_USER_ID)


@router.get(
    "/active",
    response_model=BudgetListResponse,
    summary="获取当前活跃预算",
    description="获取指定日期的活跃预算",
    responses={
        200: {"description": "获取成功", "model": BudgetListResponse},
    }
)
async def get_active_budgets(
    date: Optional[str] = Query(None, description="目标日期（YYYY-MM-DD）"),
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取指定日期的活跃预算
    
    默认获取今天的活跃预算。
    """
    budgets = await budget_service.get_active_budgets_for_date(DEFAULT_USER_ID, date)
    return {
        "budgets": budgets,
        "total": len(budgets)
    }


@router.get(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="获取预算详情",
    description="根据预算ID获取预算详细信息",
    responses={
        200: {"description": "获取成功", "model": BudgetResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def get_budget(
    budget_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算详情
    
    返回预算的详细信息，包括所有预算项目和执行情况。
    """
    budget = await budget_service.get_budget(budget_id)
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 不存在"
        )
    
    return budget


@router.put(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="更新预算",
    description="更新预算信息",
    responses={
        200: {"description": "更新成功", "model": BudgetResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def update_budget(
    budget_id: str,
    request: UpdateBudgetRequest,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    更新预算
    
    可更新名称、周期、日期、状态等。
    """
    try:
        items = None
        if request.items is not None:
            items = [item.model_dump() for item in request.items]
        
        budget = await budget_service.update_budget(
            budget_id=budget_id,
            name=request.name,
            amount=request.amount,
            period_type=request.period_type.value if request.period_type else None,
            start_date=request.start_date,
            end_date=request.end_date,
            is_active=request.is_active,
            items=items,
            cycle_type=request.cycle_type.value if request.cycle_type else None,
            carry_over_enabled=request.carry_over_enabled
        )
        
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"预算 '{budget_id}' 不存在"
            )
        
        return budget
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{budget_id}",
    response_model=MessageResponse,
    summary="删除预算",
    description="删除指定的预算",
    responses={
        200: {"description": "删除成功", "model": MessageResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def delete_budget(
    budget_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    删除预算
    
    永久删除预算及其所有项目。
    """
    result = await budget_service.delete_budget(budget_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 不存在"
        )
    
    return {"message": f"预算 '{budget_id}' 已成功删除"}


@router.post(
    "/{budget_id}/items",
    response_model=BudgetResponse,
    summary="添加预算项目",
    description="向预算添加新的预算项目",
    responses={
        200: {"description": "添加成功", "model": BudgetResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def add_budget_item(
    budget_id: str,
    request: AddBudgetItemRequest,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    添加预算项目
    
    向指定预算添加新的支出类别。
    """
    try:
        budget = await budget_service.add_budget_item(
            budget_id=budget_id,
            account_pattern=request.account_pattern,
            amount=request.amount,
            currency=request.currency
        )
        
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"预算 '{budget_id}' 不存在"
            )
        
        return budget
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{budget_id}/items/{item_id}",
    response_model=BudgetResponse,
    summary="删除预算项目",
    description="从预算中删除指定的预算项目",
    responses={
        200: {"description": "删除成功", "model": BudgetResponse},
        404: {"description": "预算或项目不存在", "model": ErrorResponse},
    }
)
async def remove_budget_item(
    budget_id: str,
    item_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    删除预算项目
    
    从预算中移除指定的支出类别。
    """
    budget = await budget_service.remove_budget_item(budget_id, item_id)
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 不存在"
        )
    
    return budget


@router.get(
    "/{budget_id}/execution",
    response_model=BudgetResponse,
    summary="获取预算执行情况",
    description="获取预算的执行情况（与获取详情相同）",
    responses={
        200: {"description": "获取成功", "model": BudgetResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def get_budget_execution(
    budget_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算执行情况
    
    返回预算的详细执行情况，包括各项目的已花费金额和使用率。
    """
    budget = await budget_service.get_budget(budget_id)
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 不存在"
        )
    
    return budget


@router.get(
    "/{budget_id}/items/{item_id}/transactions",
    response_model=dict, # 使用 dict 简化，或者使用 TransactionListResponse
    summary="获取预算项目流水",
    description="获取指定预算项目的关联交易流水",
    responses={
        200: {"description": "获取成功"},
        404: {"description": "预算或项目不存在", "model": ErrorResponse},
    }
)
async def get_budget_item_transactions(
    budget_id: str,
    item_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算项目流水
    
    返回该预算项目下关联的所有交易流水。
    """
    transactions = await budget_service.get_budget_item_transactions(budget_id, item_id)
    
    return {
        "transactions": transactions,
        "total": len(transactions)
    }


# ========== 循环预算相关端点 ==========

@router.get(
    "/{budget_id}/cycles",
    response_model=BudgetCycleListResponse,
    summary="获取预算的所有周期",
    description="获取循环预算的所有周期执行记录",
    responses={
        200: {"description": "获取成功", "model": BudgetCycleListResponse},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def get_budget_cycles(
    budget_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取预算的所有周期

    返回该预算的所有周期记录，包括每个周期的执行情况。
    """
    cycles = await budget_service.get_budget_cycles(budget_id)

    return {
        "cycles": cycles,
        "total": len(cycles)
    }


@router.get(
    "/{budget_id}/cycles/current",
    response_model=BudgetCycleResponse,
    summary="获取当前周期",
    description="获取指定日期的当前周期（默认今天）",
    responses={
        200: {"description": "获取成功", "model": BudgetCycleResponse},
        404: {"description": "预算或周期不存在", "model": ErrorResponse},
    }
)
async def get_current_budget_cycle(
    budget_id: str,
    date: Optional[str] = Query(None, description="目标日期（YYYY-MM-DD）"),
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取当前周期

    返回指定日期（默认今天）的周期执行情况。
    """
    cycle = await budget_service.get_current_budget_cycle(budget_id, date)

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 在指定日期没有活跃周期"
        )

    return cycle


@router.get(
    "/{budget_id}/cycles/summary",
    response_model=dict,
    summary="获取周期概览",
    description="获取预算周期的统计概览",
    responses={
        200: {"description": "获取成功"},
        404: {"description": "预算不存在", "model": ErrorResponse},
    }
)
async def get_budget_cycle_summary(
    budget_id: str,
    budget_service: BudgetApplicationService = Depends(get_budget_service)
):
    """
    获取周期概览

    返回周期的统计信息，包括总数、执行情况等。
    """
    summary = await budget_service.get_budget_cycle_summary(budget_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预算 '{budget_id}' 不存在"
        )

    return summary
