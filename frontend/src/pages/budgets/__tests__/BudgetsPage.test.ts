import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../../../api/accounts'
import { budgetsApi } from '../../../api/budgets'
import BudgetsPage from '../BudgetsPage.vue'

vi.mock('../../../api/accounts', () => ({
  accountsApi: { getAccounts: vi.fn() },
}))

vi.mock('../../../api/budgets', () => ({
  budgetsApi: {
    get: vi.fn(),
    save: vi.fn(),
    copyPrevious: vi.fn(),
  },
}))

const emptyBudget = { month: '2026-07', currency: 'CNY', total: '0', spent: '0', remaining: '0', items: [] }

describe('BudgetsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Expenses', account_type: 'Expenses', currencies: ['CNY'], children: [
        { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'] },
      ] },
    ])
    vi.mocked(budgetsApi.get).mockResolvedValue(emptyBudget)
  })

  it('renders monthly empty state without an unhandled error', async () => {
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('月度预算')
    expect(wrapper.text()).toContain('本月尚未设置预算')
    expect(budgetsApi.get).toHaveBeenCalledOnce()
  })

  it('adds a category and saves the monthly contract', async () => {
    vi.mocked(budgetsApi.save).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100', spent: '0', remaining: '100', risk: 'NORMAL' }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const buttons = wrapper.findAll('button')
    await buttons.find(button => button.text().includes('新增分类'))!.trigger('click')
    const inputs = wrapper.findAll('input')
    await inputs.find(input => input.attributes('placeholder') === '例如：餐饮')!.setValue('餐饮')
    await inputs.find(input => input.attributes('placeholder') === 'Expenses:Food')!.setValue('Expenses:Food')
    const amount = inputs.find(input => input.attributes('inputmode') === 'decimal')!
    await amount.setValue('100')
    await wrapper.findAll('button').find(button => button.text().includes('保存预算'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.save).toHaveBeenCalledWith(
      expect.any(String),
      'CNY',
      [expect.objectContaining({ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100' })],
    )
  })

  it('shows retryable API error', async () => {
    vi.mocked(budgetsApi.get).mockRejectedValue({ message: '投影恢复中' })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('投影恢复中')
    expect(wrapper.text()).toContain('重试')
  })
})
