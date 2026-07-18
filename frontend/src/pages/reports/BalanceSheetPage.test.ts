import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../api/reports'
import BalanceSheetPage from './BalanceSheetPage.vue'

const replace = vi.fn()
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), replace, push }),
  useRoute: () => ({ query: { as_of_date: '2026-07-31' } }),
}))
vi.mock('../../api/reports', () => ({
  reportsApi: { getBalanceSheet: vi.fn() },
}))

describe('BalanceSheetPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads balance sheet by as_of_date and formats CNY amounts as strings', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockResolvedValue({
      as_of_date: '2026-07-31',
      assets: {
        name: 'Assets',
        type: 'Assets',
        total_cny: '100.12',
        totals_by_currency: { CNY: '100.12' },
        accounts: [
          {
            account: 'Assets:Cash',
            display_name: 'Cash',
            balances: { CNY: '100.12' },
            total_cny: '100.12',
            depth: 1,
            children: [],
          },
        ],
      },
      liabilities: {
        name: 'Liabilities',
        type: 'Liabilities',
        total_cny: '0.00',
        totals_by_currency: {},
        accounts: [],
      },
      equity: {
        name: 'Equity',
        type: 'Equity',
        total_cny: '100.12',
        totals_by_currency: {},
        accounts: [],
      },
      total_assets_cny: '100.12345',
      total_liabilities_cny: '0',
      total_equity_cny: '100.12345',
      net_worth_cny: '100.12345',
      exchange_rates: { CNY: '1' },
      currencies: ['CNY'],
    })

    const wrapper = mount(BalanceSheetPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(reportsApi.getBalanceSheet).toHaveBeenCalledWith({ as_of_date: '2026-07-31' })
    expect(wrapper.text()).toContain('100.12')
    expect(wrapper.text()).toContain('资产')
  })

  it('shows retryable error when rates missing', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockRejectedValue({ message: '缺少汇率: USD' })
    const wrapper = mount(BalanceSheetPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('缺少汇率: USD')
    expect(wrapper.text()).toContain('重试')
  })
})
