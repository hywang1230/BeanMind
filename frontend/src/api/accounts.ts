import apiClient from './client'

export type Account = {
    name: string
    account_type: 'Assets' | 'Liabilities' | 'Equity' | 'Income' | 'Expenses'
    currencies: string[]
    children?: Account[]
}

export type AccountDetail = {
    name: string
    account_type: string
    currencies: string[]
    open_date?: string
    close_date?: string
    is_active: boolean
    children?: Account[]
}

export type Balance = {
    account: string
    currency: string
    amount: number
}

export type CreateAccountRequest = {
    name: string
    account_type: string
    currencies?: string[]
}

export type CloseAccountRequest = {
    close_date?: string
}

export type Transaction = {
    id: string
    date: string
    description: string
    payee: string | null
    flag: string
    postings: Array<{
        account: string
        amount: string
        currency: string
    }>
}

export type TransactionListResponse = {
    transactions: Transaction[]
    total: number
    page: number
    page_size: number
}

export const accountsApi = {
    // 获取账户树
    async getAccounts(): Promise<Account[]> {
        const response: { accounts: Account[], total: number } = await apiClient.get('/api/accounts')
        return response.accounts
    },

    // 创建账户
    createAccount(data: CreateAccountRequest): Promise<Account> {
        return apiClient.post('/api/accounts', data)
    },

    // 获取账户余额
    async getBalance(accountName: string, date?: string): Promise<Balance[]> {
        const params = date ? { date } : {}
        const response: { account_name: string, balances: Record<string, string> } = await apiClient.get(`/api/accounts/${encodeURIComponent(accountName)}/balance`, { params })

        // 将字典格式转换为数组格式
        return Object.entries(response.balances).map(([currency, amount]) => ({
            account: response.account_name,
            currency,
            amount: parseFloat(amount)
        }))
    },

    // 获取账户详情
    getAccountDetail(accountName: string): Promise<AccountDetail> {
        return apiClient.get(`/api/accounts/${encodeURIComponent(accountName)}`)
    },

    // 关闭账户
    closeAccount(accountName: string, data?: CloseAccountRequest): Promise<{ message: string }> {
        return apiClient.delete(`/api/accounts/${encodeURIComponent(accountName)}`, { data })
    },

    // 获取账户的子账户
    async getChildren(accountName: string): Promise<Account[]> {
        const response: { accounts: Account[], total: number } = await apiClient.get(`/api/accounts/${encodeURIComponent(accountName)}/children`)
        return response.accounts
    },

    // 重新开启账户
    reopenAccount(accountName: string): Promise<{ message: string }> {
        return apiClient.post(`/api/accounts/${encodeURIComponent(accountName)}/reopen`)
    }
}
