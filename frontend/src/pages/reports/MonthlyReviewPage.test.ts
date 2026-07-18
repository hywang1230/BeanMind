import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { monthlyReviewsApi, type MonthlyReview } from '../../api/monthlyReviews'
import MonthlyReportPage from './MonthlyReportPage.vue'

const replace = vi.fn()
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { month: '2026-07' } }), useRouter: () => ({ replace, back: vi.fn() }) }))
vi.mock('../../api/monthlyReviews', () => ({ monthlyReviewsApi: { get: vi.fn(), generate: vi.fn() } }))

const review: MonthlyReview = {
  report_month: '2026-07', status: 'FAILED', last_error: '模型超时', generated_at: null,
  facts: { current: { income: { CNY: '100' }, expense: { CNY: '30' } }, risk_items: [] },
  monthly_summary: '上月结余稳定', next_month_suggestions: ['保持储蓄'],
}

describe('MonthlyReviewPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('keeps last successful content visible when regeneration failed', async () => {
    vi.mocked(monthlyReviewsApi.get).mockResolvedValue(review)
    const wrapper = mount(MonthlyReportPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('模型超时')
    expect(wrapper.text()).toContain('上月结余稳定')
    expect(wrapper.text()).toContain('保持储蓄')
    expect(wrapper.text()).toContain('重新生成')
  })

  it('shows deterministic facts when LLM is disabled', async () => {
    vi.mocked(monthlyReviewsApi.get).mockResolvedValue({ ...review, status: 'DISABLED', last_error: null, monthly_summary: '', next_month_suggestions: [] })
    const wrapper = mount(MonthlyReportPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('LLM 未启用')
    expect(wrapper.text()).toContain('CNY 100')
  })
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

