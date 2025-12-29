"""
报表数据 DTO
定义资产负债表和利润表的数据结构
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import date


class AccountBalanceItem(BaseModel):
    """账户余额项"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称（不含前缀）")
    balances: Dict[str, float] = Field(default_factory=dict, description="各币种余额 {货币: 金额}")
    total_cny: float = Field(default=0, description="折合人民币总额")
    children: List["AccountBalanceItem"] = Field(default_factory=list, description="子账户列表")
    depth: int = Field(default=0, description="账户层级深度")


class BalanceSheetCategory(BaseModel):
    """资产负债表分类"""
    name: str = Field(..., description="分类名称")
    type: str = Field(..., description="类型: Assets/Liabilities/Equity")
    accounts: List[AccountBalanceItem] = Field(default_factory=list, description="账户列表")
    total_cny: float = Field(default=0, description="分类总额（人民币）")
    totals_by_currency: Dict[str, float] = Field(default_factory=dict, description="各币种总额")


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
    total_assets_cny: float = Field(default=0, description="总资产（人民币）")
    total_liabilities_cny: float = Field(default=0, description="总负债（人民币）")
    total_equity_cny: float = Field(default=0, description="总权益（人民币）")
    net_worth_cny: float = Field(default=0, description="净资产（人民币）")
    
    # 汇率信息
    exchange_rates: Dict[str, float] = Field(default_factory=dict, description="汇率表 {货币: 对CNY汇率}")
    
    # 货币列表
    currencies: List[str] = Field(default_factory=list, description="涉及的货币列表")


class IncomeExpenseItem(BaseModel):
    """收入/支出项"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称")
    amounts: Dict[str, float] = Field(default_factory=dict, description="各币种金额 {货币: 金额}")
    total_cny: float = Field(default=0, description="折合人民币总额")
    percentage: float = Field(default=0, description="占比（百分比）")
    children: List["IncomeExpenseItem"] = Field(default_factory=list, description="子账户列表")
    depth: int = Field(default=0, description="账户层级深度")


class IncomeStatementCategory(BaseModel):
    """利润表分类"""
    name: str = Field(..., description="分类名称")
    type: str = Field(..., description="类型: Income/Expenses")
    items: List[IncomeExpenseItem] = Field(default_factory=list, description="项目列表")
    total_cny: float = Field(default=0, description="分类总额（人民币）")
    totals_by_currency: Dict[str, float] = Field(default_factory=dict, description="各币种总额")


class IncomeStatementResponse(BaseModel):
    """利润表响应"""
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    
    # 收入类
    income: IncomeStatementCategory = Field(..., description="收入类账户")
    
    # 支出类
    expenses: IncomeStatementCategory = Field(..., description="支出类账户")
    
    # 汇总数据
    total_income_cny: float = Field(default=0, description="总收入（人民币）")
    total_expenses_cny: float = Field(default=0, description="总支出（人民币）")
    net_profit_cny: float = Field(default=0, description="净利润（人民币）= 收入 - 支出")
    
    # 汇率信息
    exchange_rates: Dict[str, float] = Field(default_factory=dict, description="汇率表")
    
    # 货币列表
    currencies: List[str] = Field(default_factory=list, description="涉及的货币列表")


class AccountTransactionItem(BaseModel):
    """账户交易项"""
    date: str = Field(..., description="交易日期")
    description: str = Field(..., description="交易描述")
    payee: str = Field(default="", description="交易对方")
    amount: float = Field(..., description="金额")
    currency: str = Field(default="CNY", description="货币")
    balance: float = Field(default=0, description="交易后余额")
    counterpart_accounts: List[str] = Field(default_factory=list, description="对方账户列表")


class AccountDetailResponse(BaseModel):
    """账户明细响应"""
    account: str = Field(..., description="账户名称")
    display_name: str = Field(..., description="显示名称")
    account_type: str = Field(..., description="账户类型")
    
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    
    # 当前余额
    current_balances: Dict[str, float] = Field(default_factory=dict, description="当前余额")
    current_balance_cny: float = Field(default=0, description="当前余额（人民币）")
    
    # 期初余额
    opening_balances: Dict[str, float] = Field(default_factory=dict, description="期初余额")
    opening_balance_cny: float = Field(default=0, description="期初余额（人民币）")
    
    # 本期变动
    period_change: Dict[str, float] = Field(default_factory=dict, description="本期变动")
    period_change_cny: float = Field(default=0, description="本期变动（人民币）")
    
    # 交易列表
    transactions: List[AccountTransactionItem] = Field(default_factory=list, description="交易列表")
    
    # 汇率
    exchange_rates: Dict[str, float] = Field(default_factory=dict, description="汇率表")

