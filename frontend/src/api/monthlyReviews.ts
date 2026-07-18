import apiClient from './client'

export type MonthlyReviewFacts = {
  month?: string
  currency?: string
  current?: {
    income?: string
    expense?: string
    net?: string
  }
  previous?: {
    income?: string
    expense?: string
    net?: string
  }
  changes?: {
    income_delta?: string
    expense_delta?: string
    net_delta?: string
    income_change_rate?: string | null
    expense_change_rate?: string | null
  }
  budget?: {
    currency?: string
    total?: string
    spent?: string
    remaining?: string
    usage_rate?: string | null
    items?: Array<Record<string, unknown>>
  }
  risk_items?: Array<{ name?: string; risk?: string }>
  top_expense_categories?: Array<{ name?: string; amount?: string; share?: string | null }>
  top_income_categories?: Array<{ name?: string; amount?: string; share?: string | null }>
  missing_exchange_rates?: string[]
}

export type MonthlyReview = {
  report_month: string
  status: 'DISABLED' | 'NOT_GENERATED' | 'PROCESSING' | 'READY' | 'FAILED'
  facts: MonthlyReviewFacts
  monthly_summary: string
  highlights: string[]
  next_month_suggestions: string[]
  last_error: string | null
  generated_at: string | null
}

export const monthlyReviewsApi = {
  get(month: string): Promise<MonthlyReview> {
    return apiClient.get(`/api/monthly-reviews/${month}`)
  },
  generate(month: string, regenerate = false): Promise<MonthlyReview> {
    return apiClient.post(`/api/monthly-reviews/${month}`, { regenerate })
  },
}
