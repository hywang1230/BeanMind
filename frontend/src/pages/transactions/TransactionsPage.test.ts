import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../../api/accounts'
import { transactionsApi, type Transaction } from '../../api/transactions'
import AccountPicker from '../../components/AccountPicker.vue'
import DateRangePickerField from '../../components/DateRangePickerField.vue'
import TransactionsPage from './TransactionsPage.vue'

const replace = vi.fn()
const listQuery = { transaction_type: 'expense', account: 'Expenses:Food', start_date: '2026-07-01', end_date: '2026-07-31', tags: 'food' }
const route = reactive<{ path: string; query: Record<string, string> }>({ path: '/transactions', query: { ...listQuery } })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('../../api/accounts', () => ({ accountsApi: { getAccounts: vi.fn() } }))
vi.mock('../../api/transactions', () => ({ transactionsApi: { getTransactions: vi.fn() } }))
enableAutoUnmount(afterEach)

const item: Transaction = {
  id: 'txn-1', date: '2026-07-01', description: '午餐', payee: '餐厅', transaction_type: 'expense',
  display_amounts: [{ currency: 'CNY', amount: '-20.10' }],
  postings: [{ account: 'Expenses:Food', amount: '20.10', currency: 'CNY' }, { account: 'Assets:Cash', amount: '-20.10', currency: 'CNY' }],
}

describe('TransactionsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.path = '/transactions'
    route.query = { ...listQuery }
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] },
      { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'] },
    ])
    replace.mockImplementation(({ path, query }) => {
      route.path = path
      route.query = query
    })
  })

  it('restores URL filters and appends the next cursor page', async () => {
    vi.mocked(transactionsApi.getTransactions)
      .mockResolvedValueOnce({ items: [item], next_cursor: 'next', has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, id: 'txn-2', description: '购买日用品', payee: '超市' }], next_cursor: null, has_more: false })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(transactionsApi.getTransactions).toHaveBeenCalledWith(expect.objectContaining({ transaction_type: 'expense', account: 'Expenses:Food', start_date: '2026-07-01', end_date: '2026-07-31' }))
    expect(transactionsApi.getTransactions).not.toHaveBeenCalledWith(expect.objectContaining({ tags: 'food' }))
    await wrapper.findAll('button').find(button => button.text().includes('加载更多'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('午餐')
    expect(wrapper.text()).toContain('购买日用品')
    expect(wrapper.text()).not.toContain('餐厅')
    expect(wrapper.text()).not.toContain('超市')
    expect(transactionsApi.getTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: 'next' }))
  })

  it('keeps loaded cursor pages when visiting detail and returning', async () => {
    vi.mocked(transactionsApi.getTransactions)
      .mockResolvedValueOnce({ items: [item], next_cursor: 'next', has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, id: 'txn-2', description: '第二页交易' }], next_cursor: null, has_more: false })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('加载更多'))!.trigger('click')
    await flushPromises()

    route.path = '/transactions/txn-2'
    route.query = {}
    await flushPromises()
    route.path = '/transactions'
    route.query = { ...listQuery }
    await flushPromises()

    expect(transactionsApi.getTransactions).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('午餐')
    expect(wrapper.text()).toContain('第二页交易')
  })

  it('requests the first page after submitting a new search condition', async () => {
    vi.mocked(transactionsApi.getTransactions)
      .mockResolvedValueOnce({ items: [item], next_cursor: null, has_more: false })
      .mockResolvedValueOnce({ items: [{ ...item, description: '超市购物' }], next_cursor: null, has_more: false })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    await wrapper.find('.van-search input').setValue('超市')
    wrapper.findComponent({ name: 'van-search' }).vm.$emit('search', '超市')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith(expect.objectContaining({
      path: '/transactions',
      query: expect.objectContaining({ description: '超市' }),
    }))
    expect(transactionsApi.getTransactions).toHaveBeenCalledTimes(2)
    expect(transactionsApi.getTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ description: '超市' }))
    expect(wrapper.text()).toContain('超市购物')
  })

  it('uses account selection, removes tags, and clears account and dates', async () => {
    vi.mocked(transactionsApi.getTransactions).mockResolvedValue({ items: [item], next_cursor: null, has_more: false })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('标签')
    expect(wrapper.find('input[placeholder="完整账户名"]').exists()).toBe(false)
    const accountPicker = wrapper.findComponent(AccountPicker)
    expect(accountPicker.props('accounts')).toHaveLength(2)
    expect(accountPicker.props('clearable')).toBe(true)

    accountPicker.vm.$emit('update:modelValue', 'Assets:Cash')
    accountPicker.vm.$emit('change', 'Assets:Cash')
    await flushPromises()
    expect(transactionsApi.getTransactions).toHaveBeenLastCalledWith(expect.objectContaining({ account: 'Assets:Cash' }))

    accountPicker.vm.$emit('update:modelValue', '')
    accountPicker.vm.$emit('change', '')
    await flushPromises()
    expect(replace).toHaveBeenLastCalledWith(expect.objectContaining({
      query: expect.not.objectContaining({ account: expect.anything() }),
    }))

    const dateRangePicker = wrapper.findComponent(DateRangePickerField)
    expect(dateRangePicker.props('startDate')).toBe('2026-07-01')
    expect(dateRangePicker.props('endDate')).toBe('2026-07-31')
    dateRangePicker.vm.$emit('update:startDate', '')
    dateRangePicker.vm.$emit('update:endDate', '')
    dateRangePicker.vm.$emit('change', { startDate: '', endDate: '' })
    await flushPromises()
    expect(replace).toHaveBeenLastCalledWith(expect.objectContaining({
      query: expect.not.objectContaining({
        start_date: expect.anything(),
        end_date: expect.anything(),
      }),
    }))
  })

  it('renders empty and retryable failure states', async () => {
    vi.mocked(transactionsApi.getTransactions).mockRejectedValue({ message: '查询失败' })
    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('查询失败')
    expect(wrapper.text()).toContain('重试')
  })

  it('renders description first and falls back by transaction type', async () => {
    vi.mocked(transactionsApi.getTransactions).mockResolvedValue({
      items: [
        item,
        {
          ...item,
          id: 'expense-without-description',
          description: '  ',
          display_amounts: [{ currency: 'CNY', amount: '-20' }],
          postings: [
            { account: 'Expenses:Food', amount: '10', currency: 'CNY' },
            { account: 'Expenses:Transport', amount: '10', currency: 'CNY' },
            { account: 'Assets:Cash', amount: '-20', currency: 'CNY' },
          ],
        },
        {
          ...item,
          id: 'income-without-description',
          description: undefined,
          transaction_type: 'income',
          display_amounts: [{ currency: 'CNY', amount: '100' }],
          postings: [
            { account: 'Assets:Bank', amount: '100', currency: 'CNY' },
            { account: 'Income:Salary', amount: '-80', currency: 'CNY' },
            { account: 'Income:Bonus', amount: '-20', currency: 'CNY' },
          ],
        },
        {
          ...item,
          id: 'transfer-without-description',
          description: undefined,
          transaction_type: 'transfer',
          display_amounts: [{ currency: 'CNY', amount: '-100' }],
          postings: [
            { account: 'Assets:Cash', amount: '-100', currency: 'CNY' },
            { account: 'Assets:Bank', amount: '100', currency: 'CNY' },
          ],
        },
      ],
      next_cursor: null,
      has_more: false,
    })

    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    expect(wrapper.findAll('.transaction-title').map(title => title.text())).toEqual([
      '午餐',
      'Expenses:Food，Expenses:Transport',
      'Income:Salary，Income:Bonus',
      '转账',
    ])
    expect(wrapper.findAll('.van-cell__label').map(label => label.text())).toEqual(Array(4).fill('2026-07-01'))
    expect(wrapper.text()).not.toContain('未命名交易')
    expect(wrapper.text()).not.toContain('餐厅')
  })

  it('renders backend display amounts by currency and actual direction', async () => {
    vi.mocked(transactionsApi.getTransactions).mockResolvedValue({
      items: [
        {
          ...item,
          display_amounts: [
            { currency: 'CNY', amount: '-30.30' },
            { currency: 'USD', amount: '-2.50' },
          ],
        },
        {
          ...item,
          id: 'expense-refund',
          description: '退款',
          display_amounts: [{ currency: 'CNY', amount: '5' }],
        },
        {
          ...item,
          id: 'income-reversal',
          description: '收入冲销',
          transaction_type: 'income',
          display_amounts: [{ currency: 'CNY', amount: '-10' }],
        },
      ],
      next_cursor: null,
      has_more: false,
    })

    const wrapper = mount(TransactionsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const amounts = wrapper.findAll('.transaction-list .van-cell__value span')

    expect(amounts.map(value => value.text())).toEqual([
      'CNY -30.30 / USD -2.50',
      'CNY 5',
      'CNY -10',
    ])
    expect(amounts.map(value => value.classes())).toEqual([
      ['negative'],
      ['positive'],
      ['negative'],
    ])
  })
})
