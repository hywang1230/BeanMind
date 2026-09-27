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

  it('shows signed equity components and does not open virtual report rows', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockResolvedValue({
      as_of_date: '2026-07-31',
      assets: { name: '资产', type: 'Assets', total_cny: '200', totals_by_currency: { CNY: '200' }, accounts: [] },
      liabilities: { name: '负债', type: 'Liabilities', total_cny: '120', totals_by_currency: { CNY: '120' }, accounts: [] },
      equity: {
        name: '权益', type: 'Equity', total_cny: '80', totals_by_currency: { CNY: '-20' },
        accounts: [
          { account: 'Equity:OpeningBalances', display_name: '期初权益', balances: { CNY: '-20' }, total_cny: '-20', depth: 1, children: [] },
          { account: '@equity:accumulated_result', display_name: '累计损益', balances: {}, total_cny: '100', depth: 1, children: [], is_virtual: true },
        ],
      },
      total_assets_cny: '200', total_liabilities_cny: '120', total_equity_cny: '80', net_worth_cny: '80',
      exchange_rates: { CNY: '1' }, currencies: ['CNY'],
    })

    const wrapper = mount(BalanceSheetPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('总权益80.00')
    const equityRows = wrapper.findAll('.tree-section')[2]!.findAll('.van-cell')
    expect(equityRows[0]!.text()).toContain('-20.00')
    expect(equityRows[1]!.text()).toContain('累计损益')
    expect(equityRows[1]!.text()).toContain('报表汇总项')
    await equityRows[1]!.trigger('click')
    expect(push).not.toHaveBeenCalled()
    await equityRows[0]!.trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/reports/account-detail',
      query: { account: 'Equity:OpeningBalances', end_date: '2026-07-31' },
    })
  })

  it('shows retryable error when rates missing', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockRejectedValue({ message: '缺少汇率: USD' })
    const wrapper = mount(BalanceSheetPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('缺少汇率: USD')
    expect(wrapper.text()).toContain('重试')
  })
})
