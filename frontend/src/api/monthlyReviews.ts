import apiClient from './client'

export type MonthlyReview = {
  report_month: string
  status: 'DISABLED' | 'NOT_GENERATED' | 'PROCESSING' | 'READY' | 'FAILED'
  facts: Record<string, any>
  monthly_summary: string
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
