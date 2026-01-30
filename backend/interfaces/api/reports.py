"""
报表 API 端点
提供资产负债表、利润表和账户明细查询
"""
from typing import Optional, Dict, List
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, HTTPException

from backend.interfaces.dto.reports import (
    BalanceSheetResponse,
    BalanceSheetCategory,
    AccountBalanceItem,
    IncomeStatementResponse,
    IncomeStatementCategory,
    IncomeExpenseItem,
    AccountDetailResponse,
    AccountTransactionItem,
)
from backend.config import settings
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.beancount_service import BeancountService
from beancount.core.data import Transaction, Open


router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_beancount_service() -> BeancountService:
    """获取共享的 Beancount 服务"""
    return BeancountServiceProvider.get_service(settings.LEDGER_FILE)


def get_display_name(account: str) -> str:
    """获取账户显示名称（去除顶级分类前缀）"""
    parts = account.split(":")
    if len(parts) <= 1:
        return account
    return ":".join(parts[1:])


def get_account_depth(account: str) -> int:
    """获取账户层级深度"""
    return len(account.split(":")) - 1


def build_account_tree(
    accounts_with_balances: Dict[str, Dict[str, Decimal]],
    account_type: str,
    exchange_rates: Dict[str, Decimal]
) -> List[AccountBalanceItem]:
    """
    构建账户树结构
    
    Args:
        accounts_with_balances: 账户余额字典 {账户名: {货币: 余额}}
        account_type: 账户类型前缀 (如 "Assets")
        exchange_rates: 汇率字典
    
    Returns:
        账户树列表
    """
    # 过滤指定类型的账户
    filtered_accounts = {
        acc: bal for acc, bal in accounts_with_balances.items()
        if acc.startswith(account_type + ":")
    }
    
    # 收集所有需要的中间节点路径
    all_account_paths: set = set()
    for account in filtered_accounts.keys():
        parts = account.split(":")
        # 添加所有中间路径
        for i in range(2, len(parts) + 1):
            all_account_paths.add(":".join(parts[:i]))
    
    # 构建账户层级结构
    account_tree: Dict[str, AccountBalanceItem] = {}
    
    # 首先为所有路径创建节点（包括中间节点）
    for account_path in sorted(all_account_paths):
        balances = filtered_accounts.get(account_path, {})
        
        # 计算人民币总额
        total_cny = Decimal(0)
        balance_dict = {}
        for currency, amount in balances.items():
            balance_dict[currency] = float(amount)
            rate = exchange_rates.get(currency, Decimal(1))
            total_cny += amount * rate
        
        item = AccountBalanceItem(
            account=account_path,
            display_name=get_display_name(account_path),
            balances=balance_dict,
            total_cny=float(total_cny),
            depth=get_account_depth(account_path),
            children=[]
        )
        account_tree[account_path] = item
    
    # 构建父子关系
    root_accounts: List[AccountBalanceItem] = []
    for account, item in account_tree.items():
        parts = account.split(":")
        if len(parts) <= 2:
            # 顶级账户（如 Assets:Bank）
            root_accounts.append(item)
        else:
            # 查找父账户
            parent_account = ":".join(parts[:-1])
            if parent_account in account_tree:
                account_tree[parent_account].children.append(item)
            else:
                # 父账户不存在，作为根账户
                root_accounts.append(item)
    
    # 汇总子账户余额到父账户
    def aggregate_balances(items: List[AccountBalanceItem]) -> tuple[Dict[str, float], float]:
        """递归汇总子账户余额"""
        total_balances: Dict[str, float] = defaultdict(float)
        total_cny = 0.0
        
        for item in items:
            if item.children:
                # 递归处理子账户
                child_balances, child_cny = aggregate_balances(item.children)
                # 合并子账户余额
                for currency, amount in child_balances.items():
                    total_balances[currency] += amount
                    if currency not in item.balances:
                        item.balances[currency] = 0.0
                    item.balances[currency] += amount
                # 更新该节点的 CNY 总额
                item.total_cny += child_cny
                total_cny += item.total_cny
            else:
                # 叶子节点
                for currency, amount in item.balances.items():
                    total_balances[currency] += amount
                total_cny += item.total_cny
        
        return dict(total_balances), total_cny
    
    # 执行汇总（从根节点开始）
    aggregate_balances(root_accounts)
    
    return root_accounts


def build_income_expense_tree(
    transactions: List[Dict],
    account_type: str,
    exchange_rates: Dict[str, Decimal]
) -> List[IncomeExpenseItem]:
    """
    构建收入/支出树结构
    
    Args:
        transactions: 交易列表
        account_type: 账户类型前缀 (如 "Income" 或 "Expenses")
        exchange_rates: 汇率字典
    
    Returns:
        收入/支出项列表
    """
    # 累计每个账户的金额
    account_amounts: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    
    for txn in transactions:
        for posting in txn.get("postings", []):
            account = posting.get("account", "")
            if account.startswith(account_type + ":"):
                currency = posting.get("currency", "CNY")
                amount = Decimal(str(posting.get("amount", 0)))
                account_amounts[account][currency] += amount
    
    # 收集所有需要的中间节点路径
    all_account_paths: set = set()
    for account in account_amounts.keys():
        parts = account.split(":")
        # 添加所有中间路径
        for i in range(2, len(parts) + 1):
            all_account_paths.add(":".join(parts[:i]))
    
    # 构建树结构
    account_tree: Dict[str, IncomeExpenseItem] = {}
    
    # 首先为所有路径创建节点（包括中间节点）
    for account_path in sorted(all_account_paths):
        amounts = account_amounts.get(account_path, {})
        
        # 计算人民币总额
        total_cny = Decimal(0)
        amounts_dict = {}
        for currency, amount in amounts.items():
            # Beancount 会计规则：
            # - Income 账户：收入时为负数（贷方），需要取负才能显示正确的业务金额
            # - Expenses 账户：支出时为正数（借方），直接使用即可
            if account_type == "Income":
                display_amount = float(-amount)  # 取负：负数变正数，正数变负数
            else:
                display_amount = float(amount)   # Expenses 保持原值
            
            amounts_dict[currency] = display_amount
            rate = exchange_rates.get(currency, Decimal(1))
            
            # 计算 CNY 总额时也使用相同的逻辑
            if account_type == "Income":
                total_cny += (-amount) * rate
            else:
                total_cny += amount * rate
        
        item = IncomeExpenseItem(
            account=account_path,
            display_name=get_display_name(account_path),
            amounts=amounts_dict,
            total_cny=float(total_cny),
            depth=get_account_depth(account_path),
            children=[]
        )
        account_tree[account_path] = item
    
    # 构建父子关系
    root_items: List[IncomeExpenseItem] = []
    for account, item in account_tree.items():
        parts = account.split(":")
        if len(parts) <= 2:
            root_items.append(item)
        else:
            parent_account = ":".join(parts[:-1])
            if parent_account in account_tree:
                account_tree[parent_account].children.append(item)
            else:
                root_items.append(item)
    
    # 汇总子账户金额到父账户
    def aggregate_amounts(items: List[IncomeExpenseItem]) -> tuple[Dict[str, float], float]:
        """递归汇总子账户金额"""
        total_amounts: Dict[str, float] = defaultdict(float)
        total_cny = 0.0
        
        for item in items:
            if item.children:
                # 递归处理子账户
                child_amounts, child_cny = aggregate_amounts(item.children)
                # 合并子账户金额
                for currency, amount in child_amounts.items():
                    total_amounts[currency] += amount
                    if currency not in item.amounts:
                        item.amounts[currency] = 0.0
                    item.amounts[currency] += amount
                # 更新该节点的 CNY 总额
                item.total_cny += child_cny
                total_cny += item.total_cny
            else:
                # 叶子节点
                for currency, amount in item.amounts.items():
                    total_amounts[currency] += amount
                total_cny += item.total_cny
        
        return dict(total_amounts), total_cny
    
    # 执行汇总（从根节点开始）
    aggregate_amounts(root_items)
    
    return root_items


def calculate_category_total(
    accounts: List[AccountBalanceItem]
) -> tuple[float, Dict[str, float]]:
    """计算分类总额（只计算叶子节点，避免重复计算）"""
    total_cny = 0.0
    totals_by_currency: Dict[str, float] = defaultdict(float)
    
    def process_account(account: AccountBalanceItem):
        nonlocal total_cny
        if account.children:
            # 有子账户，递归处理
            for child in account.children:
                process_account(child)
        else:
            # 叶子节点，累加
            total_cny += account.total_cny
            for currency, amount in account.balances.items():
                totals_by_currency[currency] += amount
    
    for account in accounts:
        process_account(account)
    
    return total_cny, dict(totals_by_currency)


def calculate_income_expense_total(
    items: List[IncomeExpenseItem]
) -> tuple[float, Dict[str, float]]:
    """计算收入/支出总额（只计算叶子节点）"""
    total_cny = 0.0
    totals_by_currency: Dict[str, float] = defaultdict(float)
    
    def process_item(item: IncomeExpenseItem):
        nonlocal total_cny
        if item.children:
            for child in item.children:
                process_item(child)
        else:
            total_cny += item.total_cny
            for currency, amount in item.amounts.items():
                totals_by_currency[currency] += amount
    
    for item in items:
        process_item(item)
    
    return total_cny, dict(totals_by_currency)


def calculate_percentages(items: List[IncomeExpenseItem], total: float):
    """计算占比"""
    def process_item(item: IncomeExpenseItem):
        if total > 0:
            item.percentage = (item.total_cny / total) * 100
        for child in item.children:
            process_item(child)
    
    for item in items:
        process_item(item)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    as_of_date: Optional[str] = Query(None, description="截止日期 YYYY-MM-DD，默认为今天"),
    beancount_service: BeancountService = Depends(get_beancount_service)
) -> BalanceSheetResponse:
    """
    获取资产负债表
    
    资产负债表展示某一时点的财务状况：
    - 资产 (Assets): 拥有的经济资源
    - 负债 (Liabilities): 欠他人的债务
    - 权益 (Equity): 资产减去负债后的剩余权益
    
    会计恒等式: 资产 = 负债 + 权益
    """
    # 解析日期
    if as_of_date:
        try:
            target_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    else:
        target_date = date.today()
    
    # 获取汇率
    exchange_rates = beancount_service.get_all_exchange_rates(to_currency="CNY", as_of_date=target_date)
    
    # 获取所有账户余额
    all_balances = beancount_service.get_account_balances(as_of_date=target_date)
    
    # 收集所有涉及的货币
    currencies = set()
    for balances in all_balances.values():
        currencies.update(balances.keys())
    currencies = sorted(currencies)
    
    # 构建资产类账户树
    assets_accounts = build_account_tree(all_balances, "Assets", exchange_rates)
    assets_total_cny, assets_totals_by_currency = calculate_category_total(assets_accounts)
    
    # 构建负债类账户树
    liabilities_accounts = build_account_tree(all_balances, "Liabilities", exchange_rates)
    liabilities_total_cny, liabilities_totals_by_currency = calculate_category_total(liabilities_accounts)
    
    # 构建权益类账户树
    equity_accounts = build_account_tree(all_balances, "Equity", exchange_rates)
    equity_total_cny, equity_totals_by_currency = calculate_category_total(equity_accounts)
    
    # 计算净资产 (资产 + 负债，因为负债在 beancount 中是负数)
    net_worth_cny = assets_total_cny + liabilities_total_cny
    
    return BalanceSheetResponse(
        as_of_date=target_date.isoformat(),
        assets=BalanceSheetCategory(
            name="资产",
            type="Assets",
            accounts=assets_accounts,
            total_cny=assets_total_cny,
            totals_by_currency=assets_totals_by_currency
        ),
        liabilities=BalanceSheetCategory(
            name="负债",
            type="Liabilities",
            accounts=liabilities_accounts,
            total_cny=abs(liabilities_total_cny),  # 展示为正数
            totals_by_currency={k: abs(v) for k, v in liabilities_totals_by_currency.items()}
        ),
        equity=BalanceSheetCategory(
            name="权益",
            type="Equity",
            accounts=equity_accounts,
            total_cny=abs(equity_total_cny),
            totals_by_currency={k: abs(v) for k, v in equity_totals_by_currency.items()}
        ),
        total_assets_cny=assets_total_cny,
        total_liabilities_cny=abs(liabilities_total_cny),
        total_equity_cny=abs(equity_total_cny),
        net_worth_cny=net_worth_cny,
        exchange_rates={k: float(v) for k, v in exchange_rates.items()},
        currencies=currencies
    )


@router.get("/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    beancount_service: BeancountService = Depends(get_beancount_service)
) -> IncomeStatementResponse:
    """
    获取利润表（损益表）
    
    利润表展示某一期间的经营成果：
    - 收入 (Income): 经营活动带来的经济利益流入
    - 支出 (Expenses): 经营活动导致的经济利益流出
    - 净利润 = 收入 - 支出
    """
    # 解析日期，默认为本月
    today = date.today()
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误")
    else:
        start = date(today.year, today.month, 1)
    
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误")
    else:
        end = today
    
    if start > end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    
    # 获取汇率（使用结束日期的汇率）
    exchange_rates = beancount_service.get_all_exchange_rates(to_currency="CNY", as_of_date=end)
    
    # 获取期间内的交易
    transactions = beancount_service.get_transactions(start_date=start, end_date=end)
    
    # 收集所有涉及的货币
    currencies = set()
    for txn in transactions:
        for posting in txn.get("postings", []):
            currencies.add(posting.get("currency", "CNY"))
    currencies = sorted(currencies)
    
    # 构建收入树
    income_items = build_income_expense_tree(transactions, "Income", exchange_rates)
    income_total_cny, income_totals_by_currency = calculate_income_expense_total(income_items)
    
    # 构建支出树
    expense_items = build_income_expense_tree(transactions, "Expenses", exchange_rates)
    expenses_total_cny, expenses_totals_by_currency = calculate_income_expense_total(expense_items)
    
    # 计算占比
    calculate_percentages(income_items, income_total_cny)
    calculate_percentages(expense_items, expenses_total_cny)
    
    # 计算净利润
    net_profit_cny = income_total_cny - expenses_total_cny
    
    return IncomeStatementResponse(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        income=IncomeStatementCategory(
            name="收入",
            type="Income",
            items=income_items,
            total_cny=income_total_cny,
            totals_by_currency=income_totals_by_currency
        ),
        expenses=IncomeStatementCategory(
            name="支出",
            type="Expenses",
            items=expense_items,
            total_cny=expenses_total_cny,
            totals_by_currency=expenses_totals_by_currency
        ),
        total_income_cny=income_total_cny,
        total_expenses_cny=expenses_total_cny,
        net_profit_cny=net_profit_cny,
        exchange_rates={k: float(v) for k, v in exchange_rates.items()},
        currencies=currencies
    )


@router.get("/account-detail", response_model=AccountDetailResponse)
async def get_account_detail(
    account: str = Query(..., description="账户名称"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    beancount_service: BeancountService = Depends(get_beancount_service)
) -> AccountDetailResponse:
    """
    获取账户明细
    
    展示指定账户在某一期间的交易明细，包括：
    - 期初余额
    - 本期交易列表
    - 期末余额
    """
    # 解析日期
    today = date.today()
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误")
    else:
        start = date(today.year, today.month, 1)
    
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误")
    else:
        end = today
    
    # 验证账户是否存在
    all_accounts = beancount_service.get_accounts()
    account_exists = any(acc["name"] == account for acc in all_accounts)
    if not account_exists:
        raise HTTPException(status_code=404, detail=f"账户 {account} 不存在")
    
    # 获取账户类型
    account_type = account.split(":")[0] if ":" in account else "Unknown"
    
    # 获取汇率
    exchange_rates = beancount_service.get_all_exchange_rates(to_currency="CNY", as_of_date=end)
    
    # 获取期初余额（开始日期前一天）
    opening_date = start - timedelta(days=1)
    opening_balances_raw = beancount_service.get_account_balances(account_name=account, as_of_date=opening_date)
    opening_balances = {}
    opening_balance_cny = 0.0
    if account in opening_balances_raw:
        for currency, amount in opening_balances_raw[account].items():
            opening_balances[currency] = float(amount)
            rate = exchange_rates.get(currency, Decimal(1))
            opening_balance_cny += float(amount * rate)
    
    # 获取当前余额（结束日期）
    current_balances_raw = beancount_service.get_account_balances(account_name=account, as_of_date=end)
    current_balances = {}
    current_balance_cny = 0.0
    if account in current_balances_raw:
        for currency, amount in current_balances_raw[account].items():
            current_balances[currency] = float(amount)
            rate = exchange_rates.get(currency, Decimal(1))
            current_balance_cny += float(amount * rate)
    
    # 计算本期变动
    period_change = {}
    all_currencies = set(opening_balances.keys()) | set(current_balances.keys())
    for currency in all_currencies:
        opening = opening_balances.get(currency, 0.0)
        current = current_balances.get(currency, 0.0)
        period_change[currency] = current - opening
    period_change_cny = current_balance_cny - opening_balance_cny
    
    # 获取期间内的交易
    all_transactions = beancount_service.get_transactions(start_date=start, end_date=end, account=account)
    
    # 构建交易列表
    transactions = []
    running_balance = dict(opening_balances)  # 复制期初余额
    
    for txn in all_transactions:
        # 找到当前账户的 posting
        for posting in txn.get("postings", []):
            if posting.get("account") == account:
                currency = posting.get("currency", "CNY")
                amount = posting.get("amount", 0)
                
                # 更新运行余额
                if currency not in running_balance:
                    running_balance[currency] = 0.0
                running_balance[currency] += amount
                
                # 获取对方账户
                counterpart_accounts = [
                    p.get("account") for p in txn.get("postings", [])
                    if p.get("account") != account
                ]
                
                transactions.append(AccountTransactionItem(
                    date=txn.get("date", ""),
                    description=txn.get("description", ""),
                    payee=txn.get("payee", ""),
                    amount=amount,
                    currency=currency,
                    balance=running_balance[currency],
                    counterpart_accounts=counterpart_accounts
                ))
    
    return AccountDetailResponse(
        account=account,
        display_name=get_display_name(account),
        account_type=account_type,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        current_balances=current_balances,
        current_balance_cny=current_balance_cny,
        opening_balances=opening_balances,
        opening_balance_cny=opening_balance_cny,
        period_change=period_change,
        period_change_cny=period_change_cny,
        transactions=transactions,
        exchange_rates={k: float(v) for k, v in exchange_rates.items()}
    )

