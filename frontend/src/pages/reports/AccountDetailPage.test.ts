import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi, type AccountDetailResponse } from '../../api/reports'
import AccountDetailPage from './AccountDetailPage.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
  useRoute: () => ({
    query: {
      account: 'Assets:Cash',
      start_date: '2026-07-01',
      end_date: '2026-07-31',
    },
  }),
}))
vi.mock('../../api/reports', () => ({
  reportsApi: { getAccountDetail: vi.fn() },
}))

const response: AccountDetailResponse = {
  account: 'Assets:Cash',
  display_name: 'Cash',
  account_type: 'Assets',
  start_date: '2026-07-01',
  end_date: '2026-07-31',
  current_balances: { CNY: '80.00' },
  current_balance_cny: '80.00',
  opening_balances: { CNY: '100.00' },
  opening_balance_cny: '100.00',
  period_change: { CNY: '-20.00' },
  period_change_cny: '-20.00',
  transactions: [
    {
      id: 'tx-1',
      date: '2026-07-02',
      description: '午餐',
      payee: '店',
      amount: '-20.00',
      currency: 'CNY',
      balance: '80.00',
      counterpart_accounts: ['Expenses:Food'],
    },
  ],
  exchange_rates: { CNY: '1' },
  next_cursor: 'c1',
  has_more: true,
}

describe('reports AccountDetailPage', () => {
  const wrappers: Array<ReturnType<typeof mount>> = []
  function mountPage() {
    const wrapper = mount(AccountDetailPage, { global: { plugins: [Vant] } })
    wrappers.push(wrapper)
    return wrapper
  }
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))

  it('loads account summary and first page of transactions by cursor', async () => {
    vi.mocked(reportsApi.getAccountDetail).mockResolvedValue(response)

    const wrapper = mountPage()
    await flushPromises()
    expect(reportsApi.getAccountDetail).toHaveBeenCalledWith(
      expect.objectContaining({ account: 'Assets:Cash', start_date: '2026-07-01', end_date: '2026-07-31' }),
    )
    expect(wrapper.text()).toContain('Assets:Cash')
    expect(wrapper.text()).toContain('午餐')
    expect(wrapper.text()).toContain('Expenses:Food')
    expect(wrapper.findAll('.summary-card .van-cell')[4]!.text()).toContain('-20.00')
    expect(wrapper.find('.van-list .van-cell__value').text()).toBe('CNY -20.00')
  })

  it('negates income balances, normal receipts and reversals on every page without mutating API data', async () => {
    const income: AccountDetailResponse = {
      ...response,
      account: 'Income:Investment', account_type: 'Income',
      current_balance_cny: '14197.03', opening_balance_cny: '14877.03', period_change_cny: '-680.00',
      transactions: [{ ...response.transactions[0]!, currency: 'USD', amount: '-100.00' }],
    }
    const next: AccountDetailResponse = {
      ...income,
      transactions: [{ ...response.transactions[0]!, id: 'tx-2', amount: '20.00' }],
      next_cursor: null, has_more: false,
    }
    vi.mocked(reportsApi.getAccountDetail).mockResolvedValueOnce(income).mockResolvedValueOnce(next)
    const wrapper = mountPage()
    await flushPromises()
    const summary = wrapper.findAll('.summary-card .van-cell')
    expect(summary[2]!.text()).toContain('-14197.03')
    expect(summary[3]!.text()).toContain('-14877.03')
    expect(summary[4]!.text()).toContain('680.00')
    expect(summary[4]!.text()).not.toContain('-680.00')
    expect(wrapper.find('.van-list .van-cell__value').text()).toBe('USD 100.00')
    await wrapper.findComponent({ name: 'VanList' }).vm.$emit('load')
    await flushPromises()
    expect(reportsApi.getAccountDetail).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: 'c1' }))
    expect(wrapper.findAll('.van-list .van-cell__value').map(row => row.text())).toEqual(['USD 100.00', 'CNY -20.00'])
    expect(income.current_balance_cny).toBe('14197.03')
    expect(income.transactions[0]!.amount).toBe('-100.00')
    expect(next.transactions[0]!.amount).toBe('20.00')
  })
})
