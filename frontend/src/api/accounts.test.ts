import { beforeEach, describe, expect, it, vi } from 'vitest'

import apiClient from './client'
import { accountsApi } from './accounts'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('accountsApi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists accounts and supports active_only', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      accounts: [{ name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'], is_active: true }],
      total: 1,
    })
    const items = await accountsApi.getActiveAccounts({ prefix: 'Assets' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/accounts', {
      params: { account_type: undefined, prefix: 'Assets', active_only: true },
    })
    expect(items[0]?.name).toBe('Assets:Cash')
  })

  it('creates account with open_date', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      name: 'Assets:Bank:New',
      account_type: 'Assets',
      currencies: ['CNY'],
      open_date: '2026-01-01',
      is_active: true,
    })
    await accountsApi.createAccount({
      name: 'Assets:Bank:New',
      account_type: 'Assets',
      currencies: ['CNY'],
      open_date: '2026-01-01',
    })
    expect(apiClient.post).toHaveBeenCalledWith('/api/accounts', {
      name: 'Assets:Bank:New',
      account_type: 'Assets',
      currencies: ['CNY'],
      open_date: '2026-01-01',
    })
  })
})
