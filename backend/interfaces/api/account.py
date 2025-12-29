"""账户 API 端点

提供账户管理相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from backend.config import settings
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl
from backend.application.services import AccountApplicationService
from backend.interfaces.dto.request.account import (
    CreateAccountRequest,
    CloseAccountRequest,
    SuggestAccountNameRequest
)
from backend.interfaces.dto.response.account import (
    AccountResponse,
    AccountListResponse,
    AccountBalanceResponse,
    AccountSummaryResponse,
    SuggestAccountNameResponse
)
from backend.interfaces.dto.response.auth import MessageResponse, ErrorResponse


# 创建路由
router = APIRouter(prefix="/api/accounts", tags=["账户管理"])


def get_account_service() -> AccountApplicationService:
    """
    获取账户应用服务
    
    依赖注入工厂函数。
    """
    # 获取 Beancount 服务
    beancount_service = BeancountService(settings.LEDGER_FILE)
    # 创建仓储
    account_repo = AccountRepositoryImpl(beancount_service)
    # 创建应用服务
    return AccountApplicationService(account_repo)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建账户",
    description="创建新的账户",
    responses={
        201: {"description": "创建成功", "model": AccountResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
def create_account(
    request: CreateAccountRequest,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    创建新账户
    
    需要提供账户名称、类型等信息。
    """
    try:
        account_dto = account_service.create_account(
            name=request.name,
            account_type=request.account_type,
            currencies=request.currencies,
            open_date=request.open_date
        )
        return account_dto
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "",
    response_model=AccountListResponse,
    summary="获取账户列表",
    description="获取所有账户或按条件筛选",
    responses={
        200: {"description": "获取成功", "model": AccountListResponse},
    }
)
def list_accounts(
    account_type: Optional[str] = Query(None, description="账户类型筛选"),
    prefix: Optional[str] = Query(None, description="账户名称前缀筛选"),
    active_only: bool = Query(False, description="仅显示活跃账户"),
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取账户列表
    
    支持按类型、前缀筛选，可选择仅显示活跃账户。
    """
    try:
        if account_type:
            accounts = account_service.get_accounts_by_type(account_type, active_only)
        elif prefix:
            accounts = account_service.get_accounts_by_prefix(prefix)
            if active_only:
                accounts = [acc for acc in accounts if acc["is_active"]]
        else:
            accounts = account_service.get_all_accounts(active_only)
        
        return {
            "accounts": accounts,
            "total": len(accounts)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )




@router.post(
    "/suggest-name",
    response_model=SuggestAccountNameResponse,
    summary="建议账户名称",
    description="根据账户类型和分类建议合适的账户名称",
    responses={
        200: {"description": "建议成功", "model": SuggestAccountNameResponse},
    }
)
def suggest_account_name(
    request: SuggestAccountNameRequest,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    建议账户名称
    
    根据账户类型和分类自动生成合适的账户名称。
    """
    try:
        suggested = account_service.suggest_account_name(
            request.account_type,
            request.category
        )
        is_valid = account_service.is_valid_account_name(suggested)
        
        return {
            "suggested_name": suggested,
            "is_valid": is_valid
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/roots",
    response_model=AccountListResponse,
    summary="获取根账户",
    description="获取所有根账户（顶层账户）",
    responses={
        200: {"description": "获取成功", "model": AccountListResponse},
    }
)
def list_root_accounts(
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取根账户
    
    返回所有顶层账户（如 Assets, Expenses 等）。
    """
    accounts = account_service.get_root_accounts()
    return {
        "accounts": accounts,
        "total": len(accounts)
    }


@router.get(
    "/summary",
    response_model=AccountSummaryResponse,
    summary="获取账户摘要",
    description="获取账户统计摘要信息",
    responses={
        200: {"description": "获取成功", "model": AccountSummaryResponse},
    }
)
def get_summary(
    account_type: Optional[str] = Query(None, description="账户类型筛选"),
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取账户摘要统计
    
    包含总数、活跃数、按类型统计等信息。
    """
    try:
        return account_service.get_account_summary(account_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{account_name:path}/balance",
    response_model=AccountBalanceResponse,
    summary="获取账户余额",
    description="获取指定账户的余额信息",
    responses={
        200: {"description": "获取成功", "model": AccountBalanceResponse},
    }
)
def get_account_balance(
    account_name: str,
    currency: Optional[str] = Query(None, description="指定货币"),
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取账户余额
    
    返回账户的余额信息，可指定货币。
    """
    balances = account_service.get_account_balance(account_name, currency)
    return {
        "account_name": account_name,
        "balances": balances
    }


@router.get(
    "/{account_name:path}/children",
    response_model=AccountListResponse,
    summary="获取子账户",
    description="获取指定账户的直接子账户",
    responses={
        200: {"description": "获取成功", "model": AccountListResponse},
    }
)
def get_child_accounts(
    account_name: str,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取子账户
    
    返回指定账户的所有直接子账户。
    """
    children = account_service.get_child_accounts(account_name)
    return {
        "accounts": children,
        "total": len(children)
    }


@router.get(
    "/{account_name:path}",
    response_model=AccountResponse,
    summary="获取账户详情",
    description="根据账户名称获取账户详细信息",
    responses={
        200: {"description": "获取成功", "model": AccountResponse},
        404: {"description": "账户不存在", "model": ErrorResponse},
    }
)
def get_account(
    account_name: str,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    获取账户详情
    
    根据完整的账户名称获取账户信息。
    """
    account = account_service.get_account(account_name)
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账户 '{account_name}' 不存在"
        )
    
    return account


@router.delete(
    "/{account_name:path}",
    response_model=MessageResponse,
    summary="关闭账户",
    description="关闭指定的账户",
    responses={
        200: {"description": "关闭成功", "model": MessageResponse},
        400: {"description": "无法关闭", "model": ErrorResponse},
        404: {"description": "账户不存在", "model": ErrorResponse},
    }
)
def close_account(
    account_name: str,
    request: Optional[CloseAccountRequest] = None,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    关闭账户
    
    将账户标记为关闭状态，可指定关闭日期。
    """
    try:
        close_date = request.close_date if request else None
        result = account_service.close_account(account_name, close_date)
        
        if result:
            return {"message": f"账户 '{account_name}' 已成功关闭"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 '{account_name}' 不存在"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{account_name:path}/reopen",
    response_model=MessageResponse,
    summary="重新开启账户",
    description="重新开启已关闭的账户（删除关闭记录）",
    responses={
        200: {"description": "开启成功", "model": MessageResponse},
        400: {"description": "无法开启", "model": ErrorResponse},
        404: {"description": "账户不存在", "model": ErrorResponse},
    }
)
def reopen_account(
    account_name: str,
    account_service: AccountApplicationService = Depends(get_account_service)
):
    """
    重新开启账户
    
    将已关闭的账户重新开启（删除关闭记录）。
    """
    try:
        result = account_service.reopen_account(account_name)
        
        if result:
            return {"message": f"账户 '{account_name}' 已成功重新开启"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 '{account_name}' 不存在"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
