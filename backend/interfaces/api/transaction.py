"""交易 API 端点

提供交易管理相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List

from backend.config import settings, get_db
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import TransactionRepositoryImpl, AccountRepositoryImpl
from backend.application.services import TransactionApplicationService
from backend.interfaces.dto.request.transaction import (
    CreateTransactionRequest,
    UpdateTransactionRequest,
    TransactionQueryRequest,
    StatisticsQueryRequest
)
from backend.interfaces.dto.response.transaction import (
    TransactionResponse,
    TransactionListResponse,
    TransactionStatisticsResponse,
    ValidationResultResponse,
    CategoryResponse
)
from backend.interfaces.dto.response.auth import MessageResponse, ErrorResponse


# 创建路由
router = APIRouter(prefix="/api/transactions", tags=["交易管理"])


def get_transaction_service() -> TransactionApplicationService:
    """
    获取交易应用服务
    
    依赖注入工厂函数。
    """
    # 获取 Beancount 服务
    beancount_service = BeancountService(settings.LEDGER_FILE)
    
    # 创建仓储
    transaction_repo = TransactionRepositoryImpl(beancount_service, next(get_db()))
    account_repo = AccountRepositoryImpl(beancount_service)
    
    # 创建应用服务
    return TransactionApplicationService(transaction_repo, account_repo)


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建交易",
    description="创建新的交易记录",
    responses={
        201: {"description": "创建成功", "model": TransactionResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
def create_transaction(
    request: CreateTransactionRequest,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    创建新交易
    
    需要提供交易日期、描述、记账分录等信息。
    """
    try:
        # 转换 DTO
        postings = [posting.model_dump() for posting in request.postings]
        
        transaction_dto = transaction_service.create_transaction(
            txn_date=request.date,
            description=request.description,
            postings=postings,
            payee=request.payee,
            tags=request.tags,
            links=request.links
        )
        return transaction_dto
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/payees",
    response_model=List[str],
    summary="获取所有交易方",
    description="获取历史交易中出现的所有交易方（Payee）",
    responses={
        200: {"description": "获取成功", "model": List[str]},
    }
)
def get_payees(
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    获取所有交易方
    
    返回去重后的所有交易方列表。
    """
    return transaction_service.get_all_payees()


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="获取交易列表",
    description="获取所有交易或按条件筛选",
    responses={
        200: {"description": "获取成功", "model": TransactionListResponse},
    }
)
def list_transactions(
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    account: Optional[str] = Query(None, description="账户过滤"),
    transaction_type: Optional[str] = Query(None, description="交易类型（expense/income/transfer/opening/other）"),
    tags: Optional[str] = Query(None, description="标签过滤（逗号分隔）"),
    description: Optional[str] = Query(None, description="描述关键词搜索"),
    limit: Optional[int] = Query(20, ge=1, le=1000, description="限制返回数量（1-1000）"),
    offset: Optional[int] = Query(0, ge=0, description="偏移量"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    获取交易列表
    
    支持按日期范围、账户、类型、标签等筛选，支持分页。
    """
    try:
        # 解析标签
        tag_list = tags.split(",") if tags else None
        
        transactions = transaction_service.get_transactions(
            start_date=start_date,
            end_date=end_date,
            account=account,
            transaction_type=transaction_type,
            tags=tag_list,
            description=description,
            limit=limit,
            offset=offset
        )
        
        return {
            "transactions": transactions,
            "total": len(transactions)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/statistics",
    response_model=TransactionStatisticsResponse,
    summary="获取交易统计",
    description="获取指定时间范围的交易统计信息",
    responses={
        200: {"description": "获取成功", "model": TransactionStatisticsResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
    }
)
def get_statistics(
    start_date: str = Query(..., description="开始日期（YYYY-MM-DD）"),
    end_date: str = Query(..., description="结束日期（YYYY-MM-DD）"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    获取交易统计
    
    返回指定时间范围内的交易统计信息，包括按类型、货币统计等。
    """
    try:
        return transaction_service.get_statistics(start_date, end_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="获取交易详情",
    description="根据 ID 获取交易详细信息",
    responses={
        200: {"description": "获取成功", "model": TransactionResponse},
        404: {"description": "交易不存在", "model": ErrorResponse},
    }
)
def get_transaction(
    transaction_id: str,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    获取交易详情
    
    根据交易 ID 获取完整的交易信息。
    """
    transaction = transaction_service.get_transaction_by_id(transaction_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"交易 '{transaction_id}' 不存在"
        )
    
    return transaction


@router.put(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="更新交易",
    description="更新指定的交易信息",
    responses={
        200: {"description": "更新成功", "model": TransactionResponse},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        404: {"description": "交易不存在", "model": ErrorResponse},
    }
)
def update_transaction(
    transaction_id: str,
    request: UpdateTransactionRequest,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    更新交易
    
    可以更新交易的日期、描述、记账分录等信息。
    """
    try:
        # 转换 postings
        postings = None
        if request.postings:
            postings = [posting.model_dump() for posting in request.postings]
        
        transaction_dto = transaction_service.update_transaction(
            transaction_id=transaction_id,
            txn_date=request.date,
            description=request.description,
            postings=postings,
            payee=request.payee,
            tags=request.tags,
            links=request.links
        )
        return transaction_dto
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/{transaction_id}",
    response_model=MessageResponse,
    summary="删除交易",
    description="删除指定的交易",
    responses={
        200: {"description": "删除成功", "model": MessageResponse},
        404: {"description": "交易不存在", "model": ErrorResponse},
    }
)
def delete_transaction(
    transaction_id: str,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    删除交易
    
    永久删除指定的交易记录。
    """
    result = transaction_service.delete_transaction(transaction_id)
    
    if result:
        return {"message": f"交易 '{transaction_id}' 已成功删除"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"交易 '{transaction_id}' 不存在"
        )


@router.post(
    "/validate",
    response_model=ValidationResultResponse,
    summary="验证交易",
    description="验证交易数据是否有效",
    responses={
        200: {"description": "验证完成", "model": ValidationResultResponse},
    }
)
def validate_transaction(
    request: CreateTransactionRequest,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    验证交易
    
    验证交易数据是否符合规则（借贷平衡、账户存在等）。
    """
    # 转换 DTO
    postings = [posting.model_dump() for posting in request.postings]
    
    transaction_data = {
        "date": request.date,
        "description": request.description,
        "postings": postings
    }
    
    return transaction_service.validate_transaction(transaction_data)


@router.get(
    "/{transaction_id}/category",
    response_model=CategoryResponse,
    summary="获取交易分类",
    description="获取交易的分类",
    responses={
        200: {"description": "获取成功", "model": CategoryResponse},
        404: {"description": "交易不存在", "model": ErrorResponse},
    }
)
def get_transaction_category(
    transaction_id: str,
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    获取交易分类
    
    返回交易所属的分类名称。
    """
    try:
        category = transaction_service.categorize_transaction(transaction_id)
        return {"category": category}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{transaction_id}/duplicates",
    response_model=TransactionListResponse,
    summary="查找重复交易",
    description="查找可能与此交易重复的交易",
    responses={
        200: {"description": "获取成功", "model": TransactionListResponse},
        404: {"description": "交易不存在", "model": ErrorResponse},
    }
)
def find_duplicate_transactions(
    transaction_id: str,
    tolerance_days: int = Query(1, ge=0, le=7, description="日期容差（天数，0-7）"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
):
    """
    查找重复交易
    
    根据日期、描述、金额等查找可能重复的交易。
    """
    try:
        duplicates = transaction_service.find_duplicate_transactions(
            transaction_id,
            tolerance_days
        )
        return {
            "transactions": duplicates,
            "total": len(duplicates)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
