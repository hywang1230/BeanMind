import apiClient from './client'

export type Account = {
    name: string
    account_type: 'Assets' | 'Liabilities' | 'Equity' | 'Income' | 'Expenses'
    currencies: string[]
    children?: Account[]
}

export type Balance = {
    account: string
    currency: string
    amount: number
}

export type CreateAccountRequest = {
    name: string
    type: string
    currencies?: string[]
}

export const accountsApi = {
    // 获取账户树
    getAccounts(): Promise<Account[]> {
        return apiClient.get('/api/accounts')
    },

    // 创建账户
    createAccount(data: CreateAccountRequest): Promise<Account> {
        return apiClient.post('/api/accounts', data)
    },

    // 获取账户余额
    getBalance(accountName: string, date?: string): Promise<Balance[]> {
        const params = date ? { date } : {}
        return apiClient.get(`/api/accounts/${encodeURIComponent(accountName)}/balance`, { params })
    }
}
