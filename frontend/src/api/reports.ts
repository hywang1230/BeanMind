import apiClient from './client'

// 账户余额项
export type AccountBalanceItem = {
  account: string
  display_name: string
  balances: Record<string, string>
  total_cny: string
  children: AccountBalanceItem[]
  depth: number
}

// 资产负债表分类
export type BalanceSheetCategory = {
  name: string
  type: string
  accounts: AccountBalanceItem[]
  total_cny: string
  totals_by_currency: Record<string, string>
}

// 资产负债表响应
export type BalanceSheetResponse = {
  as_of_date: string
  assets: BalanceSheetCategory
  liabilities: BalanceSheetCategory
  equity: BalanceSheetCategory
  total_assets_cny: string
  total_liabilities_cny: string
  total_equity_cny: string
  net_worth_cny: string
  exchange_rates: Record<string, string>
  currencies: string[]
}

// 收入/支出项
export type IncomeExpenseItem = {
  account: string
  display_name: string
  amounts: Record<string, string>
  total_cny: string
  percentage: string
  children: IncomeExpenseItem[]
  depth: number
}

// 利润表分类
export type IncomeStatementCategory = {
  name: string
  type: string
  items: IncomeExpenseItem[]
  total_cny: string
  totals_by_currency: Record<string, string>
}

// 利润表响应
export type IncomeStatementResponse = {
  start_date: string
  end_date: string
  income: IncomeStatementCategory
  expenses: IncomeStatementCategory
  total_income_cny: string
  total_expenses_cny: string
  net_profit_cny: string
  exchange_rates: Record<string, string>
  currencies: string[]
}

// 账户交易项
export type AccountTransactionItem = {
  id?: string
  date: string
  description: string
  payee: string
  amount: string
  currency: string
  balance: string
  counterpart_accounts: string[]
}

// 账户明细响应
export type AccountDetailResponse = {
  account: string
  display_name: string
  account_type: string
  start_date: string
  end_date: string
  current_balances: Record<string, string>
  current_balance_cny: string
  opening_balances: Record<string, string>
  opening_balance_cny: string
  period_change: Record<string, string>
  period_change_cny: string
  transactions: AccountTransactionItem[]
  exchange_rates: Record<string, string>
  next_cursor?: string | null
  has_more?: boolean
}

export type MonthlyCashflowPoint = {
  month: string
  income: string
  expense: string
  net_income: string
}

export type MissingExchangeRateMonth = {
  month: string
  currencies: string[]
}

export type MonthlyCashflowTrendResponse = {
  start_month: string
  end_month: string
  currency: string
  points: MonthlyCashflowPoint[]
  missing_exchange_rates: MissingExchangeRateMonth[]
}

export const reportsApi = {
  getBalanceSheet(params?: {
    as_of_date?: string
  }): Promise<BalanceSheetResponse> {
    return apiClient.get('/api/reports/balance-sheet', { params })
  },

  getIncomeStatement(params?: {
    start_date?: string
    end_date?: string
  }): Promise<IncomeStatementResponse> {
    return apiClient.get('/api/reports/income-statement', { params })
  },

  getAccountDetail(params: {
    account: string
    start_date?: string
    end_date?: string
    limit?: number
    cursor?: string
  }): Promise<AccountDetailResponse> {
    return apiClient.get('/api/reports/account-detail', { params })
  },

  getMonthlyCashflowTrend(params?: {
    end_month?: string
  }): Promise<MonthlyCashflowTrendResponse> {
    return apiClient.get('/api/reports/monthly-cashflow-trend', {
      params: params?.end_month ? { end_month: params.end_month } : undefined,
    })
  },
}
