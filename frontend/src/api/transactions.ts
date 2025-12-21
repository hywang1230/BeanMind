import apiClient from './client'

export type Posting = {
    account: string
    amount: number
    currency: string
}

export type Transaction = {
    id: string
    date: string
    description: string
    postings: Posting[]
    tags?: string[]
    created_at?: string
    updated_at?: string
}

export type CreateTransactionRequest = {
    date: string
    description: string
    postings: Posting[]
    tags?: string[]
}

export type TransactionsQuery = {
    page?: number
    per_page?: number
    start_date?: string
    end_date?: string
    account?: string
    description?: string
    type?: 'expense' | 'income' | 'transfer'
}

export type TransactionsResponse = {
    transactions: Transaction[]
    total: number
    page: number
    per_page: number
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
    }
}
