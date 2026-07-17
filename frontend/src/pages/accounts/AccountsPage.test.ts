import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../../api/accounts'
import AccountsPage from './AccountsPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn() }) }))
vi.mock('../../api/accounts', () => ({ accountsApi: { getAccounts: vi.fn() } }))

describe('AccountsPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders a flattened account hierarchy', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      { name: 'Assets', account_type: 'Assets', currencies: ['CNY'], children: [
        { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] },
      ] },
    ])
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Assets')
    expect(wrapper.text()).toContain('Assets:Cash')
  })

  it('renders a retryable error', async () => {
    vi.mocked(accountsApi.getAccounts).mockRejectedValue({ message: '加载失败' })
    const wrapper = mount(AccountsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).toContain('重试')
  })
})
