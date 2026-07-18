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
    expect(wrapper.text()).toContain('CNY 0')
    expect(wrapper.text()).not.toContain('请选择币种')
    expect(budgetsApi.get).toHaveBeenCalledOnce()
    expect(budgetsApi.get).toHaveBeenCalledWith(expect.any(String))
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
    const picker = wrapper.findComponent({ name: 'AccountPicker' })
    expect(picker.exists()).toBe(true)
    expect(picker.props('label')).toBe('账户')
    expect(picker.props('selectedAccounts')).toEqual([])
    await picker.vm.$emit('update:modelValue', 'Expenses:Food')
    await wrapper.vm.$nextTick()
    const amount = inputs.find(input => input.attributes('inputmode') === 'decimal')!
    await amount.setValue('100')
    await wrapper.findAll('button').find(button => button.text().includes('保存预算'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.save).toHaveBeenCalledWith(
      expect.any(String),
      [expect.objectContaining({ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100' })],
    )
  })

  it('formats usage rate to two decimal places and uses AccountPicker only', async () => {
    vi.mocked(budgetsApi.get).mockResolvedValue({
      ...emptyBudget,
      total: '15',
      spent: '70',
      remaining: '-55',
      items: [{
        name: '餐饮',
        account_pattern: 'Expenses:CY-餐饮',
        amount: '15',
        spent: '70',
        remaining: '-55',
        usage_rate: '4.666666666666666666666666667',
        risk: 'EXCEEDED',
      }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('466.67%')
    expect(wrapper.text()).not.toContain('466.6666666666666666666666667%')
    expect(wrapper.text()).not.toContain('账户范围')
    expect(wrapper.text()).not.toContain('选择账户范围')
    const picker = wrapper.findComponent({ name: 'AccountPicker' })
    expect(picker.exists()).toBe(true)
    expect(picker.props('label')).toBe('账户')
    expect(picker.props('selectedAccounts')).toEqual(['Expenses:CY-餐饮'])
    expect(wrapper.text()).toContain('CY-餐饮')
  })

  it('shows retryable API error', async () => {
    vi.mocked(budgetsApi.get).mockRejectedValue({ message: '缺少币种 USD 对 CNY 的可用汇率' })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('缺少币种 USD 对 CNY 的可用汇率')
    expect(wrapper.text()).toContain('重试')
  })

  it('pull-to-refresh reloads budget and accounts', async () => {
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const budgetCalls = vi.mocked(budgetsApi.get).mock.calls.length
    const accountCalls = vi.mocked(accountsApi.getAccounts).mock.calls.length
    expect(wrapper.find('.page-with-pull').exists()).toBe(true)
    expect(wrapper.find('.page-scroll').exists()).toBe(true)
    expect(wrapper.find('.van-pull-refresh').exists()).toBe(true)
    await wrapper.findComponent({ name: 'VanPullRefresh' }).vm.$emit('refresh')
    await flushPromises()
    expect(vi.mocked(budgetsApi.get).mock.calls.length).toBeGreaterThan(budgetCalls)
    expect(vi.mocked(accountsApi.getAccounts).mock.calls.length).toBeGreaterThan(accountCalls)
  })

  it('supports multi account patterns as comma-joined contract', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      {
        name: 'Expenses',
        account_type: 'Expenses',
        currencies: ['CNY'],
        children: [
          { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'] },
          { name: 'Expenses:Travel', account_type: 'Expenses', currencies: ['CNY'] },
        ],
      },
    ])
    vi.mocked(budgetsApi.save).mockResolvedValue({
      ...emptyBudget,
      total: '200',
      items: [{
        name: '餐饮交通',
        account_pattern: 'Expenses:Food,Expenses:Travel',
        amount: '200',
        spent: '50',
        remaining: '150',
        risk: 'NORMAL',
      }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('新增分类'))!.trigger('click')
    await wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')!.setValue('餐饮交通')
    const picker = wrapper.findComponent({ name: 'AccountPicker' })
    await picker.vm.$emit('update:modelValue', 'Expenses:Food')
    await wrapper.vm.$nextTick()
    await picker.vm.$emit('update:modelValue', 'Expenses:Travel')
    await wrapper.vm.$nextTick()
    expect(picker.props('selectedAccounts')).toEqual(['Expenses:Food', 'Expenses:Travel'])
    await wrapper.findAll('input').find(input => input.attributes('inputmode') === 'decimal')!.setValue('200')
    await wrapper.findAll('button').find(button => button.text().includes('保存预算'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.save).toHaveBeenCalledWith(
      expect.any(String),
      [expect.objectContaining({
        name: '餐饮交通',
        account_pattern: 'Expenses:Food,Expenses:Travel',
        amount: '200',
      })],
    )
    expect(wrapper.text()).toContain('Food')
    expect(wrapper.text()).toContain('Travel')
  })

  it('copies the previous month without sending a currency', async () => {
    vi.mocked(budgetsApi.copyPrevious).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100' }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('复制上月'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.copyPrevious).toHaveBeenCalledWith(expect.any(String))
    expect(
      wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')!.element.value,
    ).toBe('餐饮')
  })
})
