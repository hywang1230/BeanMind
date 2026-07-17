import apiClient from './client'

export type BudgetItem = {
  id?: string
  name: string
  account_pattern: string
  amount: string
  spent?: string
  remaining?: string
  usage_rate?: string | null
  risk?: 'NORMAL' | 'WARNING' | 'EXCEEDED'
  display_order?: number
}

export type MonthlyBudget = {
  id?: string
  month: string
  currency: string
  total: string
  spent?: string
  remaining?: string
  items: BudgetItem[]
}

export const budgetsApi = {
  get(month: string, currency = 'CNY'): Promise<MonthlyBudget> {
    return apiClient.get('/api/budgets', { params: { month, currency } })
  },
  save(month: string, currency: string, items: BudgetItem[]): Promise<MonthlyBudget> {
    return apiClient.put(`/api/budgets/${month}`, { currency, items })
  },
  copyPrevious(month: string, currency = 'CNY', overwrite = false): Promise<MonthlyBudget> {
    return apiClient.post(`/api/budgets/${month}/copy`, undefined, { params: { currency, overwrite } })
  },
}
