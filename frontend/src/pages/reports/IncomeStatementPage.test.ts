import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../api/reports'
import IncomeStatementPage from './IncomeStatementPage.vue'

const replace = vi.fn()
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), replace, push }),
  useRoute: () => ({ query: { start_date: '2026-07-01', end_date: '2026-07-31' } }),
}))
vi.mock('../../api/reports', () => ({
  reportsApi: { getIncomeStatement: vi.fn() },
}))

describe('IncomeStatementPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads income statement by closed date range and shows net profit', async () => {
    vi.mocked(reportsApi.getIncomeStatement).mockResolvedValue({
      start_date: '2026-07-01',
      end_date: '2026-07-31',
      income: {
        name: 'Income',
        type: 'Income',
        total_cny: '1000.00',
        totals_by_currency: { CNY: '1000.00' },
        items: [
          {
            account: 'Income:Salary',
            display_name: 'Salary',
            amounts: { CNY: '1000.00' },
            total_cny: '1000.00',
            percentage: '65.21739130434783',
            depth: 1,
            children: [],
          },
        ],
      },
      expenses: {
        name: 'Expenses',
        type: 'Expenses',
        total_cny: '0.12',
        totals_by_currency: { CNY: '0.12' },
        items: [],
      },
      total_income_cny: '1000.00',
      total_expenses_cny: '0.12',
      net_profit_cny: '999.88',
      exchange_rates: { CNY: '1' },
      currencies: ['CNY'],
    })

    const wrapper = mount(IncomeStatementPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(reportsApi.getIncomeStatement).toHaveBeenCalledWith({
      start_date: '2026-07-01',
      end_date: '2026-07-31',
    })
    expect(wrapper.text()).toContain('999.88')
    expect(wrapper.text()).toContain('收入')
    expect(wrapper.text()).toContain('支出')
    expect(wrapper.text()).toContain('65.22%')
    expect(wrapper.text()).not.toContain('65.21739130434783')
  })

  it('shows error state for dirty projection or missing rates', async () => {
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: '投影未就绪' })
    const wrapper = mount(IncomeStatementPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('投影未就绪')
  })
})
