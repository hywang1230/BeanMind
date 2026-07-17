import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

describe('RecurringPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})
