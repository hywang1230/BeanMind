import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../api/reports'
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

describe('reports AccountDetailPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads account summary and first page of transactions by cursor', async () => {
    vi.mocked(reportsApi.getAccountDetail).mockResolvedValue({
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
    })

    const wrapper = mount(AccountDetailPage, {
      global: {
        plugins: [Vant],
        stubs: { VanNavBar: true },
      },
    })
    await flushPromises()
    expect(reportsApi.getAccountDetail).toHaveBeenCalledWith(
      expect.objectContaining({ account: 'Assets:Cash', start_date: '2026-07-01', end_date: '2026-07-31' }),
    )
    expect(wrapper.text()).toContain('Assets:Cash')
    expect(wrapper.text()).toContain('午餐')
    expect(wrapper.text()).toContain('Expenses:Food')
  })
})
