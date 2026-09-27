import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi, type TrialBalanceResponse } from '../../api/reports'
import TrialBalancePage from './TrialBalancePage.vue'

const replace = vi.fn()
const push = vi.fn()
const route = reactive({ query: { as_of_date: '2026-07-31' } })
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), replace, push }),
  useRoute: () => route,
}))
vi.mock('../../api/reports', () => ({
  reportsApi: { getTrialBalance: vi.fn() },
}))

const response: TrialBalanceResponse = {
  as_of_date: '2026-07-31',
  categories: [
    {
      type: 'Assets', name: '资产', total_cny: '100.12', totals_by_currency: { CNY: '100.12' },
      accounts: [{
        account: 'Assets:Bank', display_name: 'Bank', balances: { CNY: '100.12' },
        total_cny: '100.12', depth: 1, children: [{
          account: 'Assets:Bank:Checking', display_name: 'Bank:Checking',
          balances: { CNY: '80.12' }, total_cny: '80.12', depth: 2, children: [],
        }],
      }],
    },
    { type: 'Liabilities', name: '负债', total_cny: '-50', totals_by_currency: { CNY: '-50' }, accounts: [] },
    { type: 'Equity', name: '权益', total_cny: '-20', totals_by_currency: { CNY: '-20' }, accounts: [] },
    { type: 'Income', name: '收入', total_cny: '-40', totals_by_currency: { CNY: '-40' }, accounts: [] },
    { type: 'Expenses', name: '支出', total_cny: '10', totals_by_currency: { CNY: '10' }, accounts: [] },
  ],
  signed_sum_cny: '0.12', ledger_error_count: 1,
  exchange_rates: { CNY: '1' }, currencies: ['CNY'],
}

describe('TrialBalancePage', () => {
  const wrappers: Array<ReturnType<typeof mount>> = []
  function mountPage() {
    const wrapper = mount(TrialBalancePage, { global: { plugins: [Vant] } })
    wrappers.push(wrapper)
    return wrapper
  }

  beforeEach(() => {
    vi.clearAllMocks()
    route.query.as_of_date = '2026-07-31'
  })
  afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))

  it('shows raw signed totals, conversion difference, and ledger warning', async () => {
    vi.mocked(reportsApi.getTrialBalance).mockResolvedValue(response)
    const wrapper = mountPage()
    await flushPromises()
    expect(reportsApi.getTrialBalance).toHaveBeenCalledWith({ as_of_date: '2026-07-31' })
    expect(wrapper.text()).toContain('五类折算合计0.12')
    const liability = wrapper.findAll('.summary-card .van-cell')[2]!
    expect(liability.text()).toContain('负债')
    expect(liability.text()).toContain('CNY -50.00')
    expect(wrapper.text()).toContain('账本加载发现 1 项错误')
    expect(wrapper.text()).toContain('不能单凭此数判断账本错误')
    expect(wrapper.findAll('.tree-section')).toHaveLength(5)
  })

  it('expands parent, opens a real account, and carries date to balance sheet', async () => {
    vi.mocked(reportsApi.getTrialBalance).mockResolvedValue(response)
    const wrapper = mountPage()
    await flushPromises()
    const rows = wrapper.findAll('.tree-section')[0]!.findAll('.van-cell')
    expect(rows).toHaveLength(1)
    await rows[0]!.trigger('click')
    expect(push).not.toHaveBeenCalled()
    await wrapper.findAll('.tree-section')[0]!.findAll('.van-cell')[1]!.trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/reports/account-detail',
      query: { account: 'Assets:Bank:Checking', end_date: '2026-07-31' },
    })
    await wrapper.findAll('.van-cell').find(cell => cell.text().includes('查看资产负债表'))!.trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/reports/balance-sheet', query: { as_of_date: '2026-07-31' },
    })
    await wrapper.find('.page-header .van-button').trigger('click')
    expect(replace).toHaveBeenCalledWith({ query: { as_of_date: '2026-07-31' } })
  })

  it('shows a retryable missing-rate error without stale totals', async () => {
    vi.mocked(reportsApi.getTrialBalance).mockRejectedValue({
      code: 'MISSING_EXCHANGE_RATE', message: '缺少币种 EUR 对 CNY 的可用汇率',
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('缺少汇率')
    expect(wrapper.text()).toContain('重试')
    expect(wrapper.text()).not.toContain('五类折算合计')
  })

  it('keeps the latest date when an older request finishes afterward', async () => {
    let resolveOld!: (value: TrialBalanceResponse) => void
    const oldRequest = new Promise<TrialBalanceResponse>(resolve => { resolveOld = resolve })
    const latest = { ...response, as_of_date: '2026-08-31', signed_sum_cny: '2.50' }
    vi.mocked(reportsApi.getTrialBalance)
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce(latest)
    const wrapper = mountPage()
    await flushPromises()
    route.query.as_of_date = '2026-08-31'
    await nextTick()
    await flushPromises()
    expect(reportsApi.getTrialBalance).toHaveBeenNthCalledWith(2, { as_of_date: '2026-08-31' })
    expect(wrapper.text()).toContain('五类折算合计2.50')
    resolveOld(response)
    await flushPromises()
    expect(wrapper.text()).toContain('五类折算合计2.50')
    expect(wrapper.text()).not.toContain('五类折算合计0.12')
    await wrapper.findAll('.van-cell').find(cell => cell.text().includes('查看资产负债表'))!.trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/reports/balance-sheet', query: { as_of_date: '2026-08-31' },
    })
  })
})
