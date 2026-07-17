import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../../api/accounts'
import AccountsPage from './AccountsPage.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn(), push }) }))
vi.mock('../../api/accounts', () => ({ accountsApi: { getAccounts: vi.fn() } }))

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
})
