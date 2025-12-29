import apiClient from './client'

// 账户余额项
export type AccountBalanceItem = {
    account: string           // 账户名称
    display_name: string      // 显示名称
    balances: Record<string, number>  // 各币种余额
    total_cny: number         // 折合人民币总额
    children: AccountBalanceItem[]  // 子账户列表
    depth: number             // 账户层级深度
}

// 资产负债表分类
export type BalanceSheetCategory = {
    name: string              // 分类名称
    type: string              // 类型: Assets/Liabilities/Equity
    accounts: AccountBalanceItem[]  // 账户列表
    total_cny: number         // 分类总额（人民币）
    totals_by_currency: Record<string, number>  // 各币种总额
}

// 资产负债表响应
export type BalanceSheetResponse = {
    as_of_date: string        // 截止日期
    assets: BalanceSheetCategory       // 资产类
    liabilities: BalanceSheetCategory  // 负债类
    equity: BalanceSheetCategory       // 权益类
    total_assets_cny: number           // 总资产（人民币）
    total_liabilities_cny: number      // 总负债（人民币）
    total_equity_cny: number           // 总权益（人民币）
    net_worth_cny: number              // 净资产（人民币）
    exchange_rates: Record<string, number>  // 汇率表
    currencies: string[]               // 涉及的货币列表
}

// 收入/支出项
export type IncomeExpenseItem = {
    account: string           // 账户名称
    display_name: string      // 显示名称
    amounts: Record<string, number>  // 各币种金额
    total_cny: number         // 折合人民币总额
    percentage: number        // 占比（百分比）
    children: IncomeExpenseItem[]  // 子账户列表
    depth: number             // 账户层级深度
}

// 利润表分类
export type IncomeStatementCategory = {
    name: string              // 分类名称
    type: string              // 类型: Income/Expenses
    items: IncomeExpenseItem[]  // 项目列表
    total_cny: number         // 分类总额（人民币）
    totals_by_currency: Record<string, number>  // 各币种总额
}

// 利润表响应
export type IncomeStatementResponse = {
    start_date: string        // 开始日期
    end_date: string          // 结束日期
    income: IncomeStatementCategory    // 收入类
    expenses: IncomeStatementCategory  // 支出类
    total_income_cny: number           // 总收入（人民币）
    total_expenses_cny: number         // 总支出（人民币）
    net_profit_cny: number             // 净利润（人民币）
    exchange_rates: Record<string, number>  // 汇率表
    currencies: string[]               // 涉及的货币列表
}

// 账户交易项
export type AccountTransactionItem = {
    date: string              // 交易日期
    description: string       // 交易描述
    payee: string             // 交易对方
    amount: number            // 金额
    currency: string          // 货币
    balance: number           // 交易后余额
    counterpart_accounts: string[]  // 对方账户列表
}

// 账户明细响应
export type AccountDetailResponse = {
    account: string           // 账户名称
    display_name: string      // 显示名称
    account_type: string      // 账户类型
    start_date: string        // 开始日期
    end_date: string          // 结束日期
    current_balances: Record<string, number>   // 当前余额
    current_balance_cny: number                // 当前余额（人民币）
    opening_balances: Record<string, number>   // 期初余额
    opening_balance_cny: number                // 期初余额（人民币）
    period_change: Record<string, number>      // 本期变动
    period_change_cny: number                  // 本期变动（人民币）
    transactions: AccountTransactionItem[]     // 交易列表
    exchange_rates: Record<string, number>     // 汇率表
}

export const reportsApi = {
    // 获取资产负债表
    getBalanceSheet(params?: {
        as_of_date?: string   // 截止日期 YYYY-MM-DD
    }): Promise<BalanceSheetResponse> {
        return apiClient.get('/api/reports/balance-sheet', { params })
    },

    // 获取利润表
    getIncomeStatement(params?: {
        start_date?: string   // 开始日期 YYYY-MM-DD
        end_date?: string     // 结束日期 YYYY-MM-DD
    }): Promise<IncomeStatementResponse> {
        return apiClient.get('/api/reports/income-statement', { params })
    },

    // 获取账户明细
    getAccountDetail(params: {
        account: string       // 账户名称
        start_date?: string   // 开始日期 YYYY-MM-DD
        end_date?: string     // 结束日期 YYYY-MM-DD
    }): Promise<AccountDetailResponse> {
        return apiClient.get('/api/reports/account-detail', { params })
    }
}

