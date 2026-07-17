import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../../api/reports'
import ReportsPage from '../ReportsPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn() }) }))
vi.mock('../../../api/reports', () => ({
  reportsApi: { getBalanceSheet: vi.fn(), getIncomeStatement: vi.fn() },
}))

describe('ReportsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders exact string amounts from retained advanced reports', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockResolvedValue({
      as_of_date: '2026-07-31', assets: {} as never, liabilities: {} as never,
      equity: {} as never, total_assets_cny: '100.123456789',
      total_liabilities_cny: '20.000000001', total_equity_cny: '80.123456788',
      net_worth_cny: '80.123456788', exchange_rates: { CNY: '1' }, currencies: ['CNY'],
    })
    vi.mocked(reportsApi.getIncomeStatement).mockResolvedValue({
      start_date: '2026-07-01', end_date: '2026-07-31', income: {} as never,
      expenses: {} as never, total_income_cny: '1000.000000001',
      total_expenses_cny: '0.123456789', net_profit_cny: '999.876543212',
      exchange_rates: { CNY: '1' }, currencies: ['CNY'],
    })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.text()).toContain('0.12')
    expect(wrapper.text()).toContain('999.88')
  })

  it('shows a retryable error', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockRejectedValue({ message: '报表加载失败' })
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: '报表加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('报表加载失败')
    expect(wrapper.text()).toContain('重试')
  })
})
