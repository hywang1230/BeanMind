import { beforeEach, describe, expect, it, vi } from 'vitest'

import apiClient from './client'
import { reportsApi } from './reports'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('reportsApi daily net spending', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls daily-net-spending with month param', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      month: '2025-01',
      currency: 'CNY',
      days: [
        {
          date: '2025-01-15',
          income: '10000.00',
          expense: '0',
          net_spending: '10000.00',
          has_activity: true,
        },
      ],
      missing_exchange_rates: [],
    })

    const result = await reportsApi.getDailyNetSpending({ month: '2025-01' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/reports/daily-net-spending', {
      params: { month: '2025-01' },
    })
    expect(result.month).toBe('2025-01')
    expect(result.days[0]?.income).toBe('10000.00')
    expect(result.days[0]?.net_spending).toBe('10000.00')
    expect(typeof result.days[0]?.income).toBe('string')
    expect(typeof result.days[0]?.expense).toBe('string')
    expect(typeof result.days[0]?.net_spending).toBe('string')
  })

  it('omits params when month is not provided', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      month: '2026-07',
      currency: 'CNY',
      days: [],
      missing_exchange_rates: [],
    })
    await reportsApi.getDailyNetSpending()
    expect(apiClient.get).toHaveBeenCalledWith('/api/reports/daily-net-spending', {
      params: undefined,
    })
  })

  it('keeps missing exchange rate contract with decimal-safe day payloads', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      month: '2025-04',
      currency: 'CNY',
      days: [
        {
          date: '2025-04-02',
          income: '0',
          expense: '-12.345',
          net_spending: '-12.345',
          has_activity: true,
        },
      ],
      missing_exchange_rates: [{ date: '2025-04-02', currencies: ['EUR'] }],
    })
    const result = await reportsApi.getDailyNetSpending({ month: '2025-04' })
    expect(result.missing_exchange_rates[0]).toEqual({
      date: '2025-04-02',
      currencies: ['EUR'],
    })
    expect(result.days[0]?.expense).toBe('-12.345')
  })
})
