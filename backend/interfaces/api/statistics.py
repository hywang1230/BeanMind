"""
统计数据 API 端点
提供资产概览、类别统计、月度趋势等数据
"""
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta

from backend.interfaces.dto.statistics import (
    AssetOverviewResponse,
    CategoryStatisticsResponse,
    MonthlyTrendResponse
)
from backend.config import settings, get_db
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl, TransactionRepositoryImpl
from backend.application.services import AccountApplicationService, TransactionApplicationService

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


def get_account_service() -> AccountApplicationService:
    """获取账户服务"""
    beancount_service = BeancountService(settings.LEDGER_FILE)
    account_repo = AccountRepositoryImpl(beancount_service)
    return AccountApplicationService(account_repo)


def get_transaction_service() -> TransactionApplicationService:
    """获取交易服务"""
    beancount_service = BeancountService(settings.LEDGER_FILE)
    transaction_repo = TransactionRepositoryImpl(beancount_service, next(get_db()))
    account_repo = AccountRepositoryImpl(beancount_service)
    return TransactionApplicationService(transaction_repo, account_repo)


@router.get("/assets", response_model=AssetOverviewResponse)
async def get_asset_overview(
    account_service: AccountApplicationService = Depends(get_account_service)
) -> AssetOverviewResponse:
    """
    获取资产概览
    
    返回净资产、总资产、总负债数据
    """
    # 获取所有账户
    all_accounts = account_service.get_all_accounts(active_only=False)
    
    total_assets = 0.0
    total_liabilities = 0.0
    
    # 统计资产和负债
    for account_dict in all_accounts:
        account_name = account_dict.get("name", "")
        
        # 获取该账户余额
        balances = account_service.get_account_balance(account_name)
        
        # 累加余额（假设使用第一个货币的余额）
        if balances:
            # balances 是一个字典，键为货币，值为余额
            for currency, amount in balances.items():
                # 资产类账户
                if account_name.startswith("Assets:"):
                    total_assets += float(amount)
                # 负债类账户（余额通常为负，取绝对值）
                elif account_name.startswith("Liabilities:"):
                    total_liabilities += abs(float(amount))
    
    # 净资产 = 总资产 - 总负债
    net_assets = total_assets - total_liabilities
    
    return AssetOverviewResponse(
        net_assets=net_assets,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        currency="CNY"
    )


@router.get("/categories", response_model=list[CategoryStatisticsResponse])
async def get_category_statistics(
    type: Literal["expense", "income"] = Query(..., description="统计类型：支出或收入"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
) -> list[CategoryStatisticsResponse]:
    """
    获取支出/收入类别统计
    
    返回指定类型的类别排名及金额
    """
    # 设置默认日期范围（本月）
    if not start_date or not end_date:
        now = datetime.now()
        start_of_month = datetime(now.year, now.month, 1)
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        start_date = start_of_month.strftime("%Y-%m-%d")
        end_date = end_of_month.strftime("%Y-%m-%d")
    
    # 获取交易列表
    transactions = transaction_service.get_transactions(
        start_date=start_date,
        end_date=end_date,
        limit=1000  # 获取足够的交易
    )
    
    # 统计类别
    category_stats: dict[str, dict] = {}
    total_amount = 0.0
    
    for transaction in transactions:
        postings = transaction.get("postings", [])
        for posting in postings:
            account = posting.get("account", "")
            
            # 判断是支出还是收入
            is_expense = account.startswith("Expenses:")
            is_income = account.startswith("Income:")
            
            # 只统计指定类型
            if type == "expense" and not is_expense:
                continue
            if type == "income" and not is_income:
                continue
            
            # 提取类别（二级账户）
            # 例如: Expenses:Food:Restaurant -> Food
            parts = account.split(":")
            if len(parts) >= 2:
                category = parts[1]
            else:
                category = "其他"
            
            # 取绝对值
            amount = abs(float(posting.get("amount", 0)))
            total_amount += amount
            
            if category not in category_stats:
                category_stats[category] = {
                    "amount": 0.0,
                    "count": 0
                }
            
            category_stats[category]["amount"] += amount
            category_stats[category]["count"] += 1
    
    # 转换为列表并排序
    result = []
    for category, stats in category_stats.items():
        percentage = (stats["amount"] / total_amount * 100) if total_amount > 0 else 0
        result.append(CategoryStatisticsResponse(
            category=category,
            amount=stats["amount"],
            percentage=percentage,
            count=stats["count"]
        ))
    
    # 按金额降序排序并限制数量
    result.sort(key=lambda x: x.amount, reverse=True)
    return result[:limit]


@router.get("/trend", response_model=list[MonthlyTrendResponse])
async def get_monthly_trend(
    months: int = Query(6, ge=1, le=24, description="返回月份数量"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
) -> list[MonthlyTrendResponse]:
    """
    获取月度趋势数据
    
    返回最近 N 个月的收入、支出、净收入趋势
    """
    result = []
    now = datetime.now()
    
    # 倒序遍历最近 N 个月
    for i in range(months - 1, -1, -1):
        # 计算目标月份
        target_month = now.month - i
        target_year = now.year
        
        # 处理跨年
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        # 计算月份的起止日期
        start_of_month = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_of_month = datetime(target_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = datetime(target_year, target_month + 1, 1) - timedelta(days=1)
        
        start_date = start_of_month.strftime("%Y-%m-%d")
        end_date = end_of_month.strftime("%Y-%m-%d")
        
        # 获取该月统计数据
        stats = transaction_service.get_statistics(start_date, end_date)
        
        # income_total 和 expense_total 是按货币的字典，取 CNY 或第一个值
        income_dict = stats.get("income_total", {})
        expense_dict = stats.get("expense_total", {})
        
        income = float(income_dict.get("CNY", sum(income_dict.values()) if income_dict else 0))
        expense = float(expense_dict.get("CNY", sum(expense_dict.values()) if expense_dict else 0))
        net = income - abs(expense)
        
        result.append(MonthlyTrendResponse(
            month=f"{target_year:04d}-{target_month:02d}",
            income=income,
            expense=abs(expense),
            net=net
        ))
    
    return result

