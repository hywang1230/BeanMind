import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { currenciesApi } from '../../../api/currencies'
import { accountsApi } from '../../../api/accounts'
import { recurringApi } from '../../../api/recurring'
import RecurringPage from '../RecurringPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn() }) }))
vi.mock('../../../api/accounts', () => ({
  accountsApi: { getAccounts: vi.fn() },
}))
vi.mock('../../../api/recurring', () => ({
  recurringApi: {
    getRules: vi.fn(), createRule: vi.fn(), updateRule: vi.fn(), executeRule: vi.fn(),
  },
}))

vi.mock('../../../api/currencies', () => ({
  currenciesApi: { listEnabledCodes: vi.fn(), list: vi.fn() },
}))

describe('RecurringPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(currenciesApi.listEnabledCodes).mockResolvedValue(['CNY', 'USD'])
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Assets', account_type: 'Assets', currencies: ['CNY'], children: [
        { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] },
      ] },
      { name: 'Expenses', account_type: 'Expenses', currencies: ['CNY'], children: [
        { name: 'Expenses:Rent', account_type: 'Expenses', currencies: ['CNY'] },
      ] },
    ])
    vi.mocked(recurringApi.getRules).mockResolvedValue([])
  })

  it('renders Vant empty state and opens the create form', async () => {
    const wrapper = mount(RecurringPage, { global: { plugins: [Vant] }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无周期任务')
    const createButtons = wrapper.findAll('button').filter(button => button.text().includes('创建规则'))
    expect(createButtons.length).toBeGreaterThan(0)
    await createButtons[0]!.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('创建周期规则')
    wrapper.unmount()
  })

  it('shows a retryable loading error', async () => {
    vi.mocked(recurringApi.getRules).mockRejectedValue({ message: '周期规则加载失败' })
    const wrapper = mount(RecurringPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('周期规则加载失败')
    expect(wrapper.text()).toContain('重试')
  })

  it('renders retained rules and supports toggling', async () => {
    const rule = {
      id: 'rule-1', name: '每月房租', frequency: 'monthly' as const,
      frequency_config: { month_days: [1] },
      transaction_template: { description: '支付房租', postings: [] },
      start_date: '2026-01-01', is_active: true,
    }
    vi.mocked(recurringApi.getRules).mockResolvedValue([rule])
    vi.mocked(recurringApi.updateRule).mockResolvedValue({ ...rule, is_active: false })
    const wrapper = mount(RecurringPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('每月房租')
    const toggle = wrapper.findAll('button').find(button => button.text() === '停用')!
    await toggle.trigger('click')
    await flushPromises()
    expect(recurringApi.updateRule).toHaveBeenCalledWith('rule-1', { is_active: false })
  })

  it('opens the edit form with existing rule and saves via updateRule', async () => {
    const rule = {
      id: 'rule-1', name: '停车费', frequency: 'monthly' as const,
      frequency_config: { month_days: [1] },
      transaction_template: {
        description: '每月停车费',
        postings: [
          { account: 'Expenses:Parking', amount: '200', currency: 'CNY' },
          { account: 'Assets:Cash', amount: '-200', currency: 'CNY' },
        ],
      },
      start_date: '2026-07-17', is_active: true,
    }
    vi.mocked(recurringApi.getRules).mockResolvedValue([rule])
    vi.mocked(recurringApi.updateRule).mockResolvedValue({ ...rule, name: '停车费-改' })
    const wrapper = mount(RecurringPage, { global: { plugins: [Vant] }, attachTo: document.body })
    await flushPromises()

    const editButton = wrapper.findAll('button').find(button => button.text() === '编辑')!
    await editButton.trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('编辑周期规则')
    expect(document.body.textContent).toContain('停车费')
    expect(document.body.textContent).toContain('每月停车费')

    const form = document.body.querySelector('form')
    expect(form).toBeTruthy()
    form!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flushPromises()

    expect(recurringApi.updateRule).toHaveBeenCalled()
    const calls = vi.mocked(recurringApi.updateRule).mock.calls
    const [id, payload] = calls[calls.length - 1]!
    expect(id).toBe('rule-1')
    expect(payload).toMatchObject({
      name: '停车费',
      frequency: 'monthly',
      frequency_config: { month_days: [1] },
      transaction_template: {
        description: '每月停车费',
        postings: [
          { account: 'Expenses:Parking', amount: '200', currency: 'CNY' },
          { account: 'Assets:Cash', amount: '-200', currency: 'CNY' },
        ],
      },
      start_date: '2026-07-17',
    })
    expect(recurringApi.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('uses SelectPickerField for posting currency in the create form', async () => {
    const wrapper = mount(RecurringPage, { global: { plugins: [Vant] }, attachTo: document.body })
    await flushPromises()
    const createButtons = wrapper.findAll('button').filter(button => button.text().includes('创建规则'))
    await createButtons[0]!.trigger('click')
    await flushPromises()

    // 币种字段应为只读选择器，而不是可自由输入的 van-field
    const currencyLabels = Array.from(document.body.querySelectorAll('.van-field')).filter((field) => {
      const label = field.querySelector('.van-field__label')
      return label?.textContent?.trim() === '币种'
    })
    expect(currencyLabels.length).toBeGreaterThan(0)
    for (const field of currencyLabels) {
      const input = field.querySelector('input') as HTMLInputElement | null
      expect(input).toBeTruthy()
      expect(input!.hasAttribute('readonly')).toBe(true)
      expect(input!.value).toBe('CNY')
    }
    wrapper.unmount()
  })

})
