"""
报表数据 DTO
定义资产负债表和利润表的数据结构
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal


class AccountBalanceItem(BaseModel):
    """账户余额项"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称（不含前缀）")
    balances: Dict[str, Decimal] = Field(default_factory=dict, description="各币种余额 {货币: 金额}")
    total_cny: Decimal = Field(default=Decimal("0"), description="折合人民币总额")
    children: List["AccountBalanceItem"] = Field(default_factory=list, description="子账户列表")
    depth: int = Field(default=0, description="账户层级深度")


class BalanceSheetCategory(BaseModel):
    """资产负债表分类"""
    name: str = Field(..., description="分类名称")
    type: str = Field(..., description="类型: Assets/Liabilities/Equity")
    accounts: List[AccountBalanceItem] = Field(default_factory=list, description="账户列表")
    total_cny: Decimal = Field(default=Decimal("0"), description="分类总额（人民币）")
    totals_by_currency: Dict[str, Decimal] = Field(default_factory=dict, description="各币种总额")


class BalanceSheetResponse(BaseModel):
    """资产负债表响应"""
    as_of_date: str = Field(..., description="截止日期 YYYY-MM-DD")
    
    # 资产类
    assets: BalanceSheetCategory = Field(..., description="资产类账户")
    
    # 负债类
    liabilities: BalanceSheetCategory = Field(..., description="负债类账户")
    
    # 权益类
    equity: BalanceSheetCategory = Field(..., description="权益类账户")
    
    # 汇总数据
    total_assets_cny: Decimal = Field(default=Decimal("0"), description="总资产（人民币）")
    total_liabilities_cny: Decimal = Field(default=Decimal("0"), description="总负债（人民币）")
    total_equity_cny: Decimal = Field(default=Decimal("0"), description="总权益（人民币）")
    net_worth_cny: Decimal = Field(default=Decimal("0"), description="净资产（人民币）")
    
    # 汇率信息
    exchange_rates: Dict[str, Decimal] = Field(default_factory=dict, description="汇率表 {货币: 对CNY汇率}")
    
    # 货币列表
    currencies: List[str] = Field(default_factory=list, description="涉及的货币列表")


class IncomeExpenseItem(BaseModel):
    """收入/支出项"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称")
    amounts: Dict[str, Decimal] = Field(default_factory=dict, description="各币种金额 {货币: 金额}")
    total_cny: Decimal = Field(default=Decimal("0"), description="折合人民币总额")
    percentage: Decimal = Field(default=Decimal("0"), description="占比（百分比）")
    children: List["IncomeExpenseItem"] = Field(default_factory=list, description="子账户列表")
    depth: int = Field(default=0, description="账户层级深度")


class IncomeStatementCategory(BaseModel):
    """利润表分类"""
    name: str = Field(..., description="分类名称")
    type: str = Field(..., description="类型: Income/Expenses")
    items: List[IncomeExpenseItem] = Field(default_factory=list, description="项目列表")
    total_cny: Decimal = Field(default=Decimal("0"), description="分类总额（人民币）")
    totals_by_currency: Dict[str, Decimal] = Field(default_factory=dict, description="各币种总额")


class IncomeStatementResponse(BaseModel):
    """利润表响应"""
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    
    # 收入类
    income: IncomeStatementCategory = Field(..., description="收入类账户")
    
    # 支出类
    expenses: IncomeStatementCategory = Field(..., description="支出类账户")
    
    # 汇总数据
    total_income_cny: Decimal = Field(default=Decimal("0"), description="总收入（人民币）")
    total_expenses_cny: Decimal = Field(default=Decimal("0"), description="总支出（人民币）")
    net_profit_cny: Decimal = Field(default=Decimal("0"), description="净利润（人民币）= 收入 - 支出")
    
    # 汇率信息
    exchange_rates: Dict[str, Decimal] = Field(default_factory=dict, description="汇率表")
    
    # 货币列表
    currencies: List[str] = Field(default_factory=list, description="涉及的货币列表")


class AccountTransactionItem(BaseModel):
    """账户交易项"""
    id: Optional[str] = Field(default=None, description="交易 ID")
    date: str = Field(..., description="交易日期")
    description: str = Field(..., description="交易描述")
    payee: str = Field(default="", description="交易对方")
    amount: Decimal = Field(..., description="金额")
    currency: str = Field(default="CNY", description="货币")
    balance: Decimal = Field(default=Decimal("0"), description="交易后余额")
    counterpart_accounts: List[str] = Field(default_factory=list, description="对方账户列表")


class AccountDetailResponse(BaseModel):
    """账户明细响应"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称")
    account_type: str = Field(..., description="账户类型")
    
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    
    # 当前余额
    current_balances: Dict[str, Decimal] = Field(default_factory=dict, description="当前余额")
    current_balance_cny: Decimal = Field(default=Decimal("0"), description="当前余额（人民币）")
    
    # 期初余额
    opening_balances: Dict[str, Decimal] = Field(default_factory=dict, description="期初余额")
    opening_balance_cny: Decimal = Field(default=Decimal("0"), description="期初余额（人民币）")
    
    # 本期变动
    period_change: Dict[str, Decimal] = Field(default_factory=dict, description="本期变动")
    period_change_cny: Decimal = Field(default=Decimal("0"), description="本期变动（人民币）")
    
    # 交易列表（Keyset Cursor 分页）
    transactions: List[AccountTransactionItem] = Field(default_factory=list, description="交易列表")
    next_cursor: Optional[str] = Field(default=None, description="下一页游标")
    has_more: bool = Field(default=False, description="是否还有更多")
    
    # 汇率
    exchange_rates: Dict[str, Decimal] = Field(default_factory=dict, description="汇率表")


class MonthlyCashflowPoint(BaseModel):
    """近 12 个月趋势中的单月点位；金额为十进制字符串。"""

    month: str = Field(..., description="月份 YYYY-MM")
    income: str = Field(..., description="经营币种收入")
    expense: str = Field(..., description="经营币种支出")
    net_income: str = Field(..., description="月净收入 = 收入 - 支出")


class MissingExchangeRateMonth(BaseModel):
    """某月缺失的折算币种。"""

    month: str = Field(..., description="月份 YYYY-MM")
    currencies: List[str] = Field(default_factory=list, description="缺失汇率的币种")


class MonthlyCashflowTrendResponse(BaseModel):
    """近 12 个月收支趋势响应。"""

    start_month: str = Field(..., description="窗口起始月 YYYY-MM")
    end_month: str = Field(..., description="窗口截止月 YYYY-MM")
    currency: str = Field(..., description="经营币种")
    points: List[MonthlyCashflowPoint] = Field(..., description="固定 12 个升序月份点位")
    missing_exchange_rates: List[MissingExchangeRateMonth] = Field(
        default_factory=list, description="按月缺失汇率"
    )


class DailyNetSpendingDay(BaseModel):
    """单日收支项。"""

    date: str = Field(..., description="日期 YYYY-MM-DD")
    income: str = Field(..., description="折算后收入（正数为收入，Decimal 字符串）")
    expense: str = Field(..., description="折算后支出（负数为支出，Decimal 字符串）")
    net_spending: str = Field(..., description="净收支 = 收入 + 支出（支出为负）")
    has_activity: bool = Field(..., description="当日是否存在 Income/Expenses 分录")


class MissingExchangeRateDay(BaseModel):
    """某日缺失的折算币种。"""

    date: str = Field(..., description="日期 YYYY-MM-DD")
    currencies: List[str] = Field(default_factory=list, description="缺失汇率的币种")


class DailyNetSpendingResponse(BaseModel):
    """指定月份每日收支响应。"""

    month: str = Field(..., description="月份 YYYY-MM")
    currency: str = Field(..., description="经营币种")
    days: List[DailyNetSpendingDay] = Field(..., description="当月全部自然日，按日期升序")
    missing_exchange_rates: List[MissingExchangeRateDay] = Field(
        default_factory=list, description="按日缺失汇率"
    )
