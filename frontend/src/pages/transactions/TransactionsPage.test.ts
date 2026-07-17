import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { transactionsApi, type Transaction } from '../../api/transactions'
import TransactionsPage from './TransactionsPage.vue'

const replace = vi.fn()
const route = { query: { transaction_type: 'expense', account: 'Expenses:Food', tags: 'food' } }
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('../../api/transactions', () => ({ transactionsApi: { getTransactions: vi.fn() } }))

const item: Transaction = {
  id: 'txn-1', date: '2026-07-01', description: '午餐', payee: '餐厅', transaction_type: 'expense',
  postings: [{ account: 'Expenses:Food', amount: '20.10', currency: 'CNY' }, { account: 'Assets:Cash', amount: '-20.10', currency: 'CNY' }],
}

describe('TransactionsPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('restores URL filters and appends the next cursor page', async () => {
    vi.mocked(transactionsApi.getTransactions)
      .mockResolvedValueOnce({ items: [item], next_cursor: 'next', has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, id: 'txn-2', payee: '超市' }], next_cursor: null, has_more: false })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(transactionsApi.getTransactions).toHaveBeenCalledWith(expect.objectContaining({ transaction_type: 'expense', account: 'Expenses:Food', tags: 'food' }))
    await wrapper.findAll('button').find(button => button.text().includes('加载更多'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('餐厅')
    expect(wrapper.text()).toContain('超市')
    expect(transactionsApi.getTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: 'next' }))
  })

  it('renders empty and retryable failure states', async () => {
    vi.mocked(transactionsApi.getTransactions).mockRejectedValue({ message: '查询失败' })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('查询失败')
    expect(wrapper.text()).toContain('重试')
  })
})
