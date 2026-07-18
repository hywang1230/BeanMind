import { flushPromises, mount } from '@vue/test-utils'
import Vant, { showConfirmDialog } from 'vant'
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

vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return {
    ...actual,
    showConfirmDialog: vi.fn(),
    showSuccessToast: vi.fn(),
  }
})

const emptyBudget = { month: '2026-07', currency: 'CNY', total: '0', spent: '0', remaining: '0', items: [] }

async function enterEdit(wrapper: ReturnType<typeof mount>) {
  const editButton = wrapper.findAll('button').find((button) => button.text().includes('编辑预算'))
  expect(editButton).toBeTruthy()
  await editButton!.trigger('click')
  await wrapper.vm.$nextTick()
}

describe('BudgetsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Expenses', account_type: 'Expenses', currencies: ['CNY'], children: [
        { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'] },
      ] },
    ])
    vi.mocked(budgetsApi.get).mockResolvedValue(emptyBudget)
    vi.mocked(showConfirmDialog).mockResolvedValue('confirm' as never)
  })

  it('renders monthly empty state without an unhandled error', async () => {
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('月度预算')
    expect(wrapper.text()).toContain('本月尚未设置预算')
    expect(wrapper.text()).toContain('CNY 0')
    expect(wrapper.text()).toContain('编辑预算')
    expect(wrapper.text()).not.toContain('请选择币种')
    expect(wrapper.text()).not.toContain('新增分类')
    expect(budgetsApi.get).toHaveBeenCalledOnce()
    expect(budgetsApi.get).toHaveBeenCalledWith(expect.any(String))
  })

  it('shows read-only categories in view mode', async () => {
    vi.mocked(budgetsApi.get).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{
        id: 'item-1',
        name: '餐饮',
        account_pattern: 'Expenses:Food',
        amount: '100',
        spent: '20',
        remaining: '80',
        usage_rate: '0.2',
        risk: 'NORMAL',
      }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('餐饮')
    expect(wrapper.text()).toContain('Expenses:Food')
    expect(wrapper.text()).toContain('100')
    expect(wrapper.text()).toContain('编辑预算')
    expect(wrapper.text()).not.toContain('删除分类')
    expect(wrapper.findAll('input')).toHaveLength(0)
  })

  it('adds a category and saves the monthly contract', async () => {
    vi.mocked(budgetsApi.save).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100', spent: '0', remaining: '100', risk: 'NORMAL' }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
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
    expect(picker.props('selectedAccounts')).toEqual(['Expenses:Food'])
    await inputs.find(input => input.attributes('inputmode') === 'decimal')!.setValue('100')
    await wrapper.findAll('button').find(button => button.text().includes('保存预算'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.save).toHaveBeenCalledWith(
      expect.any(String),
      [expect.objectContaining({ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100', display_order: 0 })],
    )
    // 保存成功回到查看态
    expect(wrapper.text()).toContain('编辑预算')
    expect(wrapper.text()).not.toContain('保存预算')
    expect(wrapper.text()).toContain('餐饮')
  })

  it('removes empty draft category without confirmation', async () => {
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
    await wrapper.findAll('button').find(button => button.text().includes('新增分类'))!.trigger('click')
    expect(wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')).toBeTruthy()
    await wrapper.findAll('button').find(button => button.text().includes('删除分类'))!.trigger('click')
    await flushPromises()
    expect(showConfirmDialog).not.toHaveBeenCalled()
    expect(wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')).toBeFalsy()
  })

  it('confirms before removing a configured category and keeps it on cancel', async () => {
    vi.mocked(budgetsApi.get).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{
        id: 'item-1',
        name: '餐饮',
        account_pattern: 'Expenses:Food',
        amount: '100',
        spent: '20',
        remaining: '80',
        risk: 'NORMAL',
      }],
    })
    vi.mocked(showConfirmDialog).mockRejectedValueOnce('cancel')
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
    await wrapper.findAll('button').find(button => button.text().includes('删除分类'))!.trigger('click')
    await flushPromises()
    expect(showConfirmDialog).toHaveBeenCalledWith(expect.objectContaining({
      title: '删除分类',
      message: expect.stringContaining('餐饮'),
    }))
    expect(wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')!.element.value).toBe('餐饮')
  })

  it('removes a configured category after confirmation', async () => {
    vi.mocked(budgetsApi.get).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{
        id: 'item-1',
        name: '餐饮',
        account_pattern: 'Expenses:Food',
        amount: '100',
      }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
    await wrapper.findAll('button').find(button => button.text().includes('删除分类'))!.trigger('click')
    await flushPromises()
    expect(showConfirmDialog).toHaveBeenCalled()
    expect(wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')).toBeFalsy()
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
    await enterEdit(wrapper)
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

  it('enables parent category selection and strips overlapping child patterns', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      {
        name: 'Expenses:JT-交通:地铁',
        account_type: 'Expenses',
        currencies: ['CNY'],
      },
      {
        name: 'Expenses:JT-交通:打车',
        account_type: 'Expenses',
        currencies: ['CNY'],
      },
    ])
    vi.mocked(budgetsApi.save).mockResolvedValue({
      ...emptyBudget,
      total: '300',
      items: [{
        name: 'JT-交通',
        account_pattern: 'Expenses:JT-交通',
        amount: '300',
        spent: '0',
        remaining: '300',
        risk: 'NORMAL',
      }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
    await wrapper.findAll('button').find(button => button.text().includes('新增分类'))!.trigger('click')
    const picker = wrapper.findComponent({ name: 'AccountPicker' })
    expect(picker.props('allowParentSelect')).toBe(true)
    // 先选子账户再选大类：范围折叠为大类；名称仅在为空时自动填充，保留首次叶子名
    await picker.vm.$emit('update:modelValue', 'Expenses:JT-交通:地铁')
    await wrapper.vm.$nextTick()
    await picker.vm.$emit('update:modelValue', 'Expenses:JT-交通:打车')
    await wrapper.vm.$nextTick()
    await picker.vm.$emit('update:modelValue', 'Expenses:JT-交通')
    await wrapper.vm.$nextTick()
    expect(picker.props('selectedAccounts')).toEqual(['Expenses:JT-交通'])
    const nameInput = wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')!
    expect(nameInput.element.value).toBe('地铁')
    await nameInput.setValue('JT-交通')
    await wrapper.findAll('input').find(input => input.attributes('inputmode') === 'decimal')!.setValue('300')
    await wrapper.findAll('button').find(button => button.text().includes('保存预算'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.save).toHaveBeenCalledWith(
      expect.any(String),
      [expect.objectContaining({
        name: 'JT-交通',
        account_pattern: 'Expenses:JT-交通',
        amount: '300',
      })],
    )
  })

  it('copies the previous month without sending a currency', async () => {
    vi.mocked(budgetsApi.copyPrevious).mockResolvedValue({
      ...emptyBudget,
      total: '100',
      items: [{ name: '餐饮', account_pattern: 'Expenses:Food', amount: '100' }],
    })
    const wrapper = mount(BudgetsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await enterEdit(wrapper)
    await wrapper.findAll('button').find(button => button.text().includes('复制上月'))!.trigger('click')
    await flushPromises()
    expect(budgetsApi.copyPrevious).toHaveBeenCalledWith(expect.any(String))
    expect(
      wrapper.findAll('input').find(input => input.attributes('placeholder') === '例如：餐饮')!.element.value,
    ).toBe('餐饮')
  })
})
