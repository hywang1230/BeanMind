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
  get(month: string): Promise<MonthlyBudget> {
    return apiClient.get('/api/budgets', { params: { month } })
  },
  save(month: string, items: BudgetItem[]): Promise<MonthlyBudget> {
    return apiClient.put(`/api/budgets/${month}`, { items })
  },
  copyPrevious(month: string, overwrite = false): Promise<MonthlyBudget> {
    return apiClient.post(`/api/budgets/${month}/copy`, undefined, { params: { overwrite } })
  },
}
