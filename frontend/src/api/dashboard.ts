import apiClient from './client'

export type Dashboard = {
  month: string
  currency: string
  income: string
  expense: string
  net_income: string
  assets: string
  liabilities: string
  net_worth: string
  budget_risk: 'NORMAL' | 'WARNING' | 'EXCEEDED'
  review_status: string
  missing_exchange_rates: string[]
}

export const dashboardApi = {
  get(month: string): Promise<Dashboard> {
    return apiClient.get('/api/dashboard', { params: { month } })
  },
}
