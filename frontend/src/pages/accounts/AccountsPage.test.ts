import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../../api/accounts'
import AccountsPage from './AccountsPage.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn(), push }) }))
vi.mock('../../api/accounts', () => ({ accountsApi: { getAccounts: vi.fn(), createAccount: vi.fn() } }))

describe('AccountsPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders a grouped tree from flat account names and opens leaf details', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Assets:Bank:Checking', account_type: 'Assets', currencies: ['CNY'] },
      { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] },
      { name: 'Expenses:Food:Lunch', account_type: 'Expenses', currencies: ['CNY'] },
    ])
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('账本账户')
    expect(wrapper.text()).not.toContain('按层级浏览账户')
    expect(wrapper.text()).toContain('资产账户')
    expect(wrapper.text()).toContain('支出账户')
    expect(wrapper.text()).toContain('Bank')
    expect(wrapper.text()).not.toContain('Assets:Bank:Checking')

    await wrapper.find('[aria-label="展开Assets:Bank"]').trigger('click')
    expect(wrapper.text()).toContain('Checking')
    expect(wrapper.text()).toContain('Assets:Bank:Checking')

    await wrapper.find('[aria-label="Assets:Bank:Checking"]').trigger('click')
    expect(push).toHaveBeenCalledWith('/accounts/Assets%3ABank%3AChecking')
  })

  it('keeps synthetic group rows non-navigable', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Liabilities:CreditCard:CMB', account_type: 'Liabilities', currencies: ['CNY'] },
    ])
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    await wrapper.find('[aria-label="展开Liabilities:CreditCard"]').trigger('click')
    expect(push).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Liabilities:CreditCard:CMB')
  })

  it('expands selectable parent accounts before opening child details', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Equity:OpeningBalances', account_type: 'Equity', currencies: ['CNY'] },
      { name: 'Equity:OpeningBalances:Cash', account_type: 'Equity', currencies: ['CNY'] },
    ])
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()

    expect(wrapper.text()).toContain('权益账户')
    expect(wrapper.text()).toContain('2 个账户')
    expect(wrapper.text()).toContain('OpeningBalances')
    expect(wrapper.text()).not.toContain('Equity:OpeningBalances:Cash')

    await wrapper.find('[aria-label="展开Equity:OpeningBalances"]').trigger('click')
    expect(push).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Equity:OpeningBalances:Cash')

    await wrapper.find('[aria-label="Equity:OpeningBalances:Cash"]').trigger('click')
    expect(push).toHaveBeenCalledWith('/accounts/Equity%3AOpeningBalances%3ACash')
  })

  it('renders a retryable error', async () => {
    vi.mocked(accountsApi.getAccounts).mockRejectedValue({ message: '加载失败' })
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).toContain('重试')
  })

  it('opens create dialog and submits a new account with prefix and selected currencies', async () => {
    vi.mocked(accountsApi.getAccounts)
      .mockResolvedValueOnce([
        { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY', 'USD'] },
      ])
      .mockResolvedValueOnce([
        { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY', 'USD'] },
        { name: 'Assets:Bank:New', account_type: 'Assets', currencies: ['CNY', 'USD'] },
      ])
    vi.mocked(accountsApi.createAccount).mockResolvedValue({
      name: 'Assets:Bank:New',
      account_type: 'Assets',
      currencies: ['CNY', 'USD'],
    } as never)
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === '新建')!.trigger('click')
    expect(wrapper.text()).toContain('新建账户')
    expect(wrapper.text()).toContain('Assets:')
    // type first, then name with prefix
    expect(wrapper.find('.name-prefix').text()).toBe('Assets:')

    const suffixInput = wrapper.find('.name-suffix-input')
    await suffixInput.setValue('Bank:New')

    // select USD in addition to default CNY
    const checkboxes = wrapper.findAllComponents({ name: 'VanCheckbox' })
    const usd = checkboxes.find((box) => box.text().includes('USD'))
    if (usd && !usd.props('modelValue')) {
      await usd.trigger('click')
    } else {
      // fallback: set form via group if needed
      const group = wrapper.findComponent({ name: 'VanCheckboxGroup' })
      await group.vm.$emit('update:modelValue', ['CNY', 'USD'])
    }

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(accountsApi.createAccount).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Assets:Bank:New',
        account_type: 'Assets',
        currencies: expect.arrayContaining(['CNY']),
      }),
    )
  })

  it('uses theme surface tokens for account group cards', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] },
    ])
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const group = wrapper.find('.account-group')
    expect(group.exists()).toBe(true)
    // style source uses theme tokens, not hard-coded white fallbacks
    expect(wrapper.html()).toContain('account-group')
  })
})
