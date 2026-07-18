import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { monthlyReviewsApi, type MonthlyReview } from '../../api/monthlyReviews'
import MonthlyReportPage from './MonthlyReportPage.vue'

const replace = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { month: '2026-07' } }),
  useRouter: () => ({ replace, back: vi.fn() }),
}))
vi.mock('../../api/monthlyReviews', () => ({
  monthlyReviewsApi: { get: vi.fn(), generate: vi.fn() },
}))

const review: MonthlyReview = {
  report_month: '2026-07',
  status: 'FAILED',
  last_error: '模型超时',
  generated_at: null,
  facts: {
    currency: 'CNY',
    current: { income: '100', expense: '30', net: '70' },
    changes: { income_change_rate: null, expense_change_rate: '0.1' },
    risk_items: [],
    missing_exchange_rates: [],
  },
  monthly_summary: '上月结余稳定',
  highlights: ['结余为正'],
  next_month_suggestions: ['保持储蓄'],
}

describe('MonthlyReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps last successful content visible when regeneration failed', async () => {
    vi.mocked(monthlyReviewsApi.get).mockResolvedValue(review)
    const wrapper = mount(MonthlyReportPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('模型超时')
    expect(wrapper.text()).toContain('上月结余稳定')
    expect(wrapper.text()).toContain('保持储蓄')
    expect(wrapper.text()).toContain('结余为正')
    expect(wrapper.text()).toContain('重新生成')
  })

  it('shows operating-currency deterministic facts when LLM is disabled', async () => {
    vi.mocked(monthlyReviewsApi.get).mockResolvedValue({
      ...review,
      status: 'DISABLED',
      last_error: null,
      monthly_summary: '',
      highlights: [],
      next_month_suggestions: [],
      facts: {
        currency: 'CNY',
        current: { income: '100', expense: '30', net: '70' },
        risk_items: [{ name: '餐饮', risk: 'WARNING' }],
        missing_exchange_rates: ['USD'],
      },
    })
    const wrapper = mount(MonthlyReportPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('LLM 未启用')
    expect(wrapper.text()).toContain('CNY 100')
    expect(wrapper.text()).toContain('CNY 30')
    expect(wrapper.text()).toContain('CNY 70')
    expect(wrapper.text()).toContain('USD')
    expect(wrapper.text()).not.toContain('CNY 100 / USD')
  })

  it('formats generated_at without ISO T and fractional seconds', async () => {
    vi.mocked(monthlyReviewsApi.get).mockResolvedValue({
      ...review,
      status: 'READY',
      last_error: null,
      generated_at: '2026-07-18T01:09:32.856991',
    })
    const wrapper = mount(MonthlyReportPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('已生成')
    expect(wrapper.text()).toContain('2026-07-18 01:09:32')
    expect(wrapper.text()).not.toContain('2026-07-18T01:09:32')
    expect(wrapper.text()).not.toContain('.856991')
  })
})
