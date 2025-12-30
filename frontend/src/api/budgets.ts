import apiClient from './client'

// 预算状态枚举
export type BudgetStatus = 'normal' | 'warning' | 'exceeded'

// 周期类型枚举
export type PeriodType = 'MONTHLY' | 'YEARLY' | 'CUSTOM'

// 预算项目
export type BudgetItem = {
    id: string
    budget_id: string
    account_pattern: string
    amount: number
    currency: string
    spent: number
    remaining: number
    usage_rate: number
    status: BudgetStatus
}

// 预算
export type Budget = {
    id: string
    name: string
    period_type: PeriodType
    start_date: string
    end_date: string | null
    is_active: boolean
    items: BudgetItem[]
    total_budget: number
    total_spent: number
    total_remaining: number
    overall_usage_rate: number
    status: BudgetStatus
    created_at?: string
    updated_at?: string
}

// 预算列表响应
export type BudgetListResponse = {
    budgets: Budget[]
    total: number
}

// 预算概览
export type BudgetSummary = {
    total_budgets: number
    active_budgets: number
    total_budgeted: number
    total_spent: number
    overall_rate: number
    status_count: {
        normal: number
        warning: number
        exceeded: number
    }
}

// 创建预算项目请求
export type CreateBudgetItemRequest = {
    account_pattern: string
    amount?: number
    currency?: string
}

// 创建预算请求
export type CreateBudgetRequest = {
    name: string
    amount: number
    period_type: PeriodType
    start_date: string
    end_date?: string
    items?: CreateBudgetItemRequest[]
}

// 更新预算请求
export type UpdateBudgetRequest = {
    name?: string
    amount?: number
    period_type?: PeriodType
    start_date?: string
    end_date?: string
    is_active?: boolean
    items?: CreateBudgetItemRequest[]
}

import type { Transaction } from './accounts'

// 预算流水响应
export type BudgetItemTransactionListResponse = {
    transactions: Transaction[]
    total: number
}

export const budgetsApi = {
    // 获取预算列表
    getBudgets(isActive?: boolean): Promise<BudgetListResponse> {
        const params = isActive !== undefined ? { is_active: isActive } : {}
        return apiClient.get('/api/budgets', { params })
    },

    // 获取活跃预算
    getActiveBudgets(date?: string): Promise<BudgetListResponse> {
        const params = date ? { date } : {}
        return apiClient.get('/api/budgets/active', { params })
    },

    // 获取预算概览
    getBudgetSummary(): Promise<BudgetSummary> {
        return apiClient.get('/api/budgets/summary')
    },

    // 创建预算
    createBudget(data: CreateBudgetRequest): Promise<Budget> {
        return apiClient.post('/api/budgets', data)
    },

    // 获取预算详情
    getBudget(id: string): Promise<Budget> {
        return apiClient.get(`/api/budgets/${id}`)
    },

    // 更新预算
    updateBudget(id: string, data: UpdateBudgetRequest): Promise<Budget> {
        return apiClient.put(`/api/budgets/${id}`, data)
    },

    // 删除预算
    deleteBudget(id: string): Promise<{ message: string }> {
        return apiClient.delete(`/api/budgets/${id}`)
    },

    // 添加预算项目
    addBudgetItem(budgetId: string, item: CreateBudgetItemRequest): Promise<Budget> {
        return apiClient.post(`/api/budgets/${budgetId}/items`, item)
    },

    // 删除预算项目
    removeBudgetItem(budgetId: string, itemId: string): Promise<Budget> {
        return apiClient.delete(`/api/budgets/${budgetId}/items/${itemId}`)
    },

    // 获取预算执行情况
    getBudgetExecution(budgetId: string): Promise<Budget> {
        return apiClient.get(`/api/budgets/${budgetId}/execution`)
    },

    // 获取预算项目流水
    getBudgetItemTransactions(budgetId: string, itemId: string): Promise<BudgetItemTransactionListResponse> {
        return apiClient.get(`/api/budgets/${budgetId}/items/${itemId}/transactions`)
    }
}
