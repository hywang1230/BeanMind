import apiClient from './client'

export type Posting = {
    account: string
    amount: string
    currency: string
}

export type Transaction = {
    id: string
    date: string
    description?: string
    payee?: string
    postings: Posting[]
    tags?: string[]
    transaction_type?: 'expense' | 'income' | 'transfer' | 'opening' | 'other'
    created_at?: string
    updated_at?: string
    meta?: {
        filename?: string
        lineno?: number
        [key: string]: any
    }
}

export type CreateTransactionRequest = {
    date: string
    description?: string
    payee?: string
    postings: Posting[]
    tags?: string[]
}

export type TransactionsQuery = {
    limit?: number
    offset?: number
    start_date?: string
    end_date?: string
    account?: string
    description?: string
    transaction_type?: 'expense' | 'income' | 'transfer'
}

export type TransactionsResponse = {
    transactions: Transaction[]
    total: number
}

export type TransactionStatistics = {
    total_income: number
    total_expense: number
    net_amount: number
    currency: string
}

export const transactionsApi = {
    // 获取交易列表
    getTransactions(query: TransactionsQuery = {}): Promise<TransactionsResponse> {
        return apiClient.get('/api/transactions', { params: query })
    },

    // 创建交易
    createTransaction(data: CreateTransactionRequest): Promise<Transaction> {
        return apiClient.post('/api/transactions', data)
    },

    // 获取交易详情
    getTransaction(id: string): Promise<Transaction> {
        return apiClient.get(`/api/transactions/${id}`)
    },

    // 更新交易
    updateTransaction(id: string, data: Partial<CreateTransactionRequest>): Promise<Transaction> {
        return apiClient.put(`/api/transactions/${id}`, data)
    },

    // 删除交易
    deleteTransaction(id: string): Promise<void> {
        return apiClient.delete(`/api/transactions/${id}`)
    },

    // 获取统计数据
    getStatistics(startDate?: string, endDate?: string): Promise<TransactionStatistics> {
        const params: any = {}
        if (startDate) params.start_date = startDate
        if (endDate) params.end_date = endDate
        return apiClient.get('/api/transactions/statistics', { params })
    },

    // 获取所有交易方
    getPayees(): Promise<string[]> {
        return apiClient.get('/api/transactions/payees')
    },

    // 获取汇率（货币到 CNY）
    getExchangeRates(): Promise<Record<string, number>> {
        return apiClient.get('/api/transactions/exchange-rates')
    }
}
