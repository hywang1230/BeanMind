import apiClient, { type ApiError } from './client'

export const UNCONFIRMED_TRANSACTION_MESSAGE = '未能确认操作结果，请刷新核对，勿重复提交'

function writeError(error: ApiError): never {
    if (error.code === 'REQUEST_NO_RESPONSE') {
        throw { ...error, code: 'TRANSACTION_RESULT_UNCONFIRMED', message: UNCONFIRMED_TRANSACTION_MESSAGE } satisfies ApiError
    }
    throw error
}

const writeOptions = { timeout: 60000 }

export type Posting = {
    account: string
    amount: string
    currency: string
}

export type DisplayAmount = {
    currency: string
    amount: string
}

export type Transaction = {
    id: string
    date: string
    description?: string
    payee?: string
    postings: Posting[]
    display_amounts: DisplayAmount[]
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
    cursor?: string
    start_date?: string
    end_date?: string
    account?: string
    tags?: string
    description?: string
    transaction_type?: 'expense' | 'income' | 'transfer'
}

export type TransactionsResponse = {
    items: Transaction[]
    next_cursor: string | null
    has_more: boolean
}

export type TransactionStatistics = {
    total_income: string
    total_expense: string
    net_amount: string
    currency: string
}

export const transactionsApi = {
    // 获取交易列表
    getTransactions(query: TransactionsQuery = {}): Promise<TransactionsResponse> {
        return apiClient.get('/api/transactions', { params: query })
    },

    // 创建交易
    createTransaction(data: CreateTransactionRequest): Promise<Transaction> {
        return apiClient.post<Transaction, Transaction>('/api/transactions', data, writeOptions).catch(writeError)
    },

    // 获取交易详情
    getTransaction(id: string): Promise<Transaction> {
        return apiClient.get(`/api/transactions/${id}`)
    },

    // 更新交易
    updateTransaction(id: string, data: Partial<CreateTransactionRequest>): Promise<Transaction> {
        return apiClient.put<Transaction, Transaction>(`/api/transactions/${id}`, data, writeOptions).catch(writeError)
    },

    // 删除交易
    deleteTransaction(id: string): Promise<void> {
        return apiClient.delete<void, void>(`/api/transactions/${id}`, writeOptions).catch(writeError)
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
    getExchangeRates(): Promise<Record<string, string>> {
        return apiClient.get('/api/transactions/exchange-rates')
    }
}
