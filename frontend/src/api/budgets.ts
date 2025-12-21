import apiClient from './client'

export type Budget = {
    id: number
    name: string
    period_type: 'monthly' | 'quarterly' | 'yearly'
    start_date: string
    end_date: string
    items: BudgetItem[]
    created_at?: string
    updated_at?: string
}

export type BudgetItem = {
    id: number
    budget_id: number
    account_pattern: string
    amount: number
    currency: string
}

export type BudgetExecution = {
    budget_id: number
    budget_name: string
    period_start: string
    period_end: string
    items: BudgetItemExecution[]
    total_budget: number
    total_actual: number
    total_remaining: number
    status: 'normal' | 'warning' | 'exceeded'
}

export type BudgetItemExecution = {
    item_id: number
    account_pattern: string
    budget_amount: number
    actual_amount: number
    remaining_amount: number
    usage_rate: number
    status: 'normal' | 'warning' | 'exceeded'
}

export type CreateBudgetRequest = {
    name: string
    period_type: 'monthly' | 'quarterly' | 'yearly'
    start_date: string
    end_date?: string
    items: {
        account_pattern: string
        amount: number
        currency: string
    }[]
}

export const budgetsApi = {
    // 获取预算列表
    getBudgets(): Promise<Budget[]> {
        return apiClient.get('/api/budgets')
    },

    // 创建预算
    createBudget(data: CreateBudgetRequest): Promise<Budget> {
        return apiClient.post('/api/budgets', data)
    },

    // 获取预算详情
    getBudget(id: number): Promise<Budget> {
        return apiClient.get(`/api/budgets/${id}`)
    },

    // 更新预算
    updateBudget(id: number, data: Partial<CreateBudgetRequest>): Promise<Budget> {
        return apiClient.put(`/api/budgets/${id}`, data)
    },

    // 删除预算
    deleteBudget(id: number): Promise<void> {
        return apiClient.delete(`/api/budgets/${id}`)
    },

    // 获取预算执行情况
    getBudgetExecution(budgetId: number, date?: string): Promise<BudgetExecution> {
        const params = date ? { date } : {}
        return apiClient.get(`/api/budgets/${budgetId}/execution`, { params })
    }
}
