import apiClient from './client'

export type AccountType = 'Assets' | 'Liabilities' | 'Equity' | 'Income' | 'Expenses'

export type Account = {
  name: string
  account_type: AccountType | string
  currencies: string[]
  is_active?: boolean
  open_date?: string | null
  close_date?: string | null
  depth?: number
  parent?: string | null
  meta?: Record<string, unknown>
  children?: Account[]
}

export type AccountDetail = {
  name: string
  account_type: string
  currencies: string[]
  open_date?: string | null
  close_date?: string | null
  is_active: boolean
  depth?: number
  parent?: string | null
  children?: Account[]
}

export type Balance = {
  account: string
  currency: string
  amount: string
}

export type CreateAccountRequest = {
  name: string
  account_type: string
  currencies?: string[]
  open_date?: string
}

export type CloseAccountRequest = {
  close_date?: string
}

export type ListAccountsQuery = {
  account_type?: string
  prefix?: string
  active_only?: boolean
}

export const accountsApi = {
  async getAccounts(query: ListAccountsQuery = {}): Promise<Account[]> {
    const response: { accounts: Account[]; total: number } = await apiClient.get('/api/accounts', {
      params: {
        account_type: query.account_type,
        prefix: query.prefix,
        active_only: query.active_only,
      },
    })
    return response.accounts
  },

  /** Active accounts for pickers. */
  async getActiveAccounts(query: Omit<ListAccountsQuery, 'active_only'> = {}): Promise<Account[]> {
    return this.getAccounts({ ...query, active_only: true })
  },

  createAccount(data: CreateAccountRequest): Promise<Account> {
    return apiClient.post('/api/accounts', data)
  },

  async getBalance(accountName: string, date?: string): Promise<Balance[]> {
    const params = date ? { date } : {}
    const response: { account_name: string; balances: Record<string, string> } = await apiClient.get(
      `/api/accounts/${encodeURIComponent(accountName)}/balance`,
      { params },
    )
    return Object.entries(response.balances).map(([currency, amount]) => ({
      account: response.account_name,
      currency,
      amount,
    }))
  },

  getAccountDetail(accountName: string): Promise<AccountDetail> {
    return apiClient.get(`/api/accounts/${encodeURIComponent(accountName)}`)
  },

  closeAccount(accountName: string, data?: CloseAccountRequest): Promise<{ message: string }> {
    return apiClient.delete(`/api/accounts/${encodeURIComponent(accountName)}`, { data })
  },

  async getChildren(accountName: string): Promise<Account[]> {
    const response: { accounts: Account[]; total: number } = await apiClient.get(
      `/api/accounts/${encodeURIComponent(accountName)}/children`,
    )
    return response.accounts
  },

  reopenAccount(accountName: string): Promise<{ message: string }> {
    return apiClient.post(`/api/accounts/${encodeURIComponent(accountName)}/reopen`)
  },
}
