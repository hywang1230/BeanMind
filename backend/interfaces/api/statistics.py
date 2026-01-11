"""
统计数据 API 端点
提供资产概览、类别统计、月度趋势等数据
"""
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from decimal import Decimal

from backend.interfaces.dto.statistics import (
    AssetOverviewResponse,
    CategoryStatisticsResponse,
    MonthlyTrendResponse,
    FrequentItemResponse
)
from backend.config import settings, get_db
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.repositories import AccountRepositoryImpl, TransactionRepositoryImpl
from backend.application.services import AccountApplicationService, TransactionApplicationService

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


def get_beancount_service():
    """获取共享的 BeancountService 实例"""
    return BeancountServiceProvider.get_service(settings.LEDGER_FILE)


def get_account_service() -> AccountApplicationService:
    """获取账户服务"""
    beancount_service = get_beancount_service()
    account_repo = AccountRepositoryImpl(beancount_service)
    return AccountApplicationService(account_repo)


def get_transaction_service() -> TransactionApplicationService:
    """获取交易服务"""
    beancount_service = get_beancount_service()
    transaction_repo = TransactionRepositoryImpl(beancount_service, next(get_db()))
    account_repo = AccountRepositoryImpl(beancount_service)
    return TransactionApplicationService(transaction_repo, account_repo)


def get_exchange_rates(as_of_date: datetime = None, target_currency: str = None) -> dict:
    """
    获取所有货币到目标货币的汇率
    
    Args:
        as_of_date: 截止日期，用于获取该日期或之前最近的汇率
        target_currency: 目标货币，如果为 None 则使用账本的主币种
    
    Returns:
        汇率字典 {货币代码: 汇率}，例如 {"USD": 7.13, "CNY": 1}
    """
    beancount_service = get_beancount_service()
    # 如果未指定目标货币，使用账本的主币种
    if target_currency is None:
        target_currency = beancount_service.get_operating_currency()
    # 转换为 date 类型
    date_obj = as_of_date.date() if as_of_date else None
    rates = beancount_service.get_all_exchange_rates(to_currency=target_currency, as_of_date=date_obj)
    return {k: float(v) for k, v in rates.items()}


def convert_to_operating_currency(amount: float, currency: str, exchange_rates: dict) -> float:
    """
    将金额转换为主币种（使用提供的汇率字典）
    
    Args:
        amount: 原始金额
        currency: 原始货币
        exchange_rates: 汇率字典
    
    Returns:
        转换后的金额
    """
    rate = exchange_rates.get(currency, 1.0)
    return amount * rate


@router.get("/assets", response_model=AssetOverviewResponse)
async def get_asset_overview() -> AssetOverviewResponse:
    """
    获取资产概览
    
    返回净资产、总资产、总负债数据（统一转换为账本主币种）
    
    Beancount 会计恒等式：Assets + Liabilities + Equity = 0
    - 资产（Assets）：正数表示拥有的价值
    - 负债（Liabilities）：负数表示欠款
    - 净资产 = 资产 + 负债（因为负债是负数，所以等价于 资产 - |负债|）
    
    多币种处理：使用 beancount 账本中的 price 指令获取汇率，将所有货币转换为主币种
    """
    # 获取共享的 Beancount 服务
    beancount_service = get_beancount_service()
    
    # 获取账本的主币种
    operating_currency = beancount_service.get_operating_currency()
    
    # 获取所有货币到主币种的汇率
    exchange_rates = beancount_service.get_all_exchange_rates(to_currency=operating_currency)
    
    # 一次性批量获取所有账户余额（性能优化：避免逐账户查询）
    all_balances = beancount_service.get_account_balances()
    
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")  # 存储负债原始值（负数）
    
    # 统计资产和负债
    for account_name, balances in all_balances.items():
        # 累加余额
        for currency, amount in balances.items():
            # 获取汇率，如果没有则默认为 1（假设是主币种）
            rate = exchange_rates.get(currency, Decimal("1"))
            
            # 转换为主币种
            amount_in_currency = amount * rate
            
            # 资产类账户：正数表示拥有的价值
            if account_name.startswith("Assets:"):
                total_assets += amount_in_currency
            # 负债类账户：负数表示欠款，直接累加原始值
            elif account_name.startswith("Liabilities:"):
                total_liabilities += amount_in_currency
    
    # 净资产 = 资产 + 负债（负债为负数）
    net_assets = total_assets + total_liabilities
    
    # 返回时，负债取绝对值用于展示（用户更容易理解"欠了多少钱"）
    return AssetOverviewResponse(
        net_assets=float(net_assets),
        total_assets=float(total_assets),
        total_liabilities=float(abs(total_liabilities)),  # 展示为正数
        currency=operating_currency
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
    
    返回指定类型的类别排名及金额（统一转换为 CNY）
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
    
    # 获取汇率
    exchange_rates = get_exchange_rates()
    
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
            
            # 获取金额和货币，转换为主币种
            raw_amount = float(posting.get("amount", 0))
            currency = posting.get("currency", "CNY")
            amount_converted = abs(convert_to_operating_currency(raw_amount, currency, exchange_rates))
            
            total_amount += amount_converted
            
            if category not in category_stats:
                category_stats[category] = {
                    "amount": 0.0,
                    "count": 0
                }
            
            category_stats[category]["amount"] += amount_converted
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
    
    返回最近 N 个月的收入、支出、净收入趋势（统一转换为 CNY）
    
    性能优化：一次性获取汇率，避免每月重复获取
    """
    result = []
    now = datetime.now()
    
    # 性能优化：一次性获取当前汇率（用于所有月份的转换）
    # 对于历史趋势，使用当前汇率是合理的近似
    exchange_rates = get_exchange_rates()
    
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
        
        # 获取该月统计数据（由于使用了单例提供者，性能已大幅提升）
        stats = transaction_service.get_statistics(start_date, end_date)
        
        # income_total 和 expense_total 是按货币的字典
        # 将所有货币转换为主币种后累加
        income_dict = stats.get("income_total", {})
        expense_dict = stats.get("expense_total", {})
        
        # 转换并累加所有货币的收入
        income = 0.0
        for currency, amount in income_dict.items():
            income += convert_to_operating_currency(float(amount), currency, exchange_rates)
        
        # 转换并累加所有货币的支出
        expense = 0.0
        for currency, amount in expense_dict.items():
            expense += convert_to_operating_currency(float(amount), currency, exchange_rates)
        
        net = income - abs(expense)
        
        result.append(MonthlyTrendResponse(
            month=f"{target_year:04d}-{target_month:02d}",
            income=income,
            expense=abs(expense),
            net=net
        ))

    return result


@router.get("/frequent", response_model=list[FrequentItemResponse])
async def get_frequent_items(
    type: Literal["expense", "income", "transfer", "account"] = Query(..., description="类型：支出/收入/转账/账户"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    limit: int = Query(3, ge=1, le=10, description="返回数量限制"),
    transaction_service: TransactionApplicationService = Depends(get_transaction_service)
) -> list[FrequentItemResponse]:
    """
    获取常用账户/分类

    返回最近N天内使用频率最高的账户或分类（Top 3）

    统计规则：
    - expense: 返回支出交易中最常用的分类（Expenses:*）
    - income: 返回收入交易中最常用的分类（Income:*）
    - transfer: 返回转账交易中最常用的账户（Assets:* 和 Liabilities:*）
    - account: 返回所有交易中最常用的账户（Assets:* 和 Liabilities:*）
    """
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # 获取交易列表
    transactions = transaction_service.get_transactions(
        start_date=start_date_str,
        end_date=end_date_str,
        limit=1000  # 获取足够的交易
    )

    # 统计账户/分类使用频率
    item_stats: dict[str, dict] = {}

    for transaction in transactions:
        postings = transaction.get("postings", [])
        txn_date = transaction.get("date", "")

        # 判断交易类型
        is_expense = any(p.get("account", "").startswith("Expenses:") for p in postings)
        is_income = any(p.get("account", "").startswith("Income:") for p in postings)
        is_transfer = any(
            p.get("account", "").startswith("Assets:") or p.get("account", "").startswith("Liabilities:")
            for p in postings
        )

        # 根据类型筛选
        if type == "expense" and not is_expense:
            continue
        if type == "income" and not is_income:
            continue
        if type == "transfer" and not is_transfer:
            continue

        # 统计每个账户/分类（使用完整的末级账户路径）
        for posting in postings:
            account = posting.get("account", "")

            # 根据类型过滤账户
            if type == "expense":
                # 只统计支出分类（末级）
                if not account.startswith("Expenses:"):
                    continue
            elif type == "income":
                # 只统计收入分类（末级）
                if not account.startswith("Income:"):
                    continue
            elif type in ["transfer", "account"]:
                # 统计资产和负债账户（末级）
                if not (account.startswith("Assets:") or account.startswith("Liabilities:")):
                    continue

            # 使用完整的账户名称（beancount posting通常使用末级账户）
            # 不需要额外处理，account已经是完整的末级账户路径

            # 统计使用次数
            if account not in item_stats:
                item_stats[account] = {
                    "count": 0,
                    "last_used": txn_date
                }

            item_stats[account]["count"] += 1
            # 更新最后使用日期
            if txn_date > item_stats[account]["last_used"]:
                item_stats[account]["last_used"] = txn_date

    # 转换为列表并按使用次数排序
    result = []
    for name, stats in item_stats.items():
        result.append(FrequentItemResponse(
            name=name,
            count=stats["count"],
            last_used=stats["last_used"]
        ))

    # 按使用次数降序排序并限制数量
    result.sort(key=lambda x: (x.count, x.last_used), reverse=True)
    return result[:limit]
