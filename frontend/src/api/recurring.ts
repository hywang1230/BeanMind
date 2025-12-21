import apiClient from './client'

export type RecurringRule = {
    id: number
    name: string
    frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'yearly'
    frequency_config: FrequencyConfig
    transaction_template: TransactionTemplate
    start_date: string
    end_date?: string
    is_active: boolean
    created_at?: string
    updated_at?: string
}

export type FrequencyConfig = {
    weekdays?: number[]  // 1-7 (Monday-Sunday)
    month_days?: number[]  // 1-31 or -1 for last day
    months?: number[]  // 1-12
}

export type TransactionTemplate = {
    description: string
    postings: {
        account: string
        amount: number
        currency: string
    }[]
    tags?: string[]
}

export type RecurringExecution = {
    id: number
    rule_id: number
    execution_date: string
    transaction_id?: string
    status: 'pending' | 'executed' | 'failed'
    error_message?: string
    created_at?: string
}

export type CreateRecurringRuleRequest = {
    name: string
    frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'yearly'
    frequency_config: FrequencyConfig
    transaction_template: TransactionTemplate
    start_date: string
    end_date?: string
    is_active?: boolean
}

export const recurringApi = {
    // 获取周期规则列表
    getRules(): Promise<RecurringRule[]> {
        return apiClient.get('/api/recurring/rules')
    },

    // 创建周期规则
    createRule(data: CreateRecurringRuleRequest): Promise<RecurringRule> {
        return apiClient.post('/api/recurring/rules', data)
    },

    // 获取规则详情
    getRule(id: number): Promise<RecurringRule> {
        return apiClient.get(`/api/recurring/rules/${id}`)
    },

    // 更新规则
    updateRule(id: number, data: Partial<CreateRecurringRuleRequest>): Promise<RecurringRule> {
        return apiClient.put(`/api/recurring/rules/${id}`, data)
    },

    // 删除规则
    deleteRule(id: number): Promise<void> {
        return apiClient.delete(`/api/recurring/rules/${id}`)
    },

    // 手动执行规则
    executeRule(id: number, date: string): Promise<RecurringExecution> {
        return apiClient.post(`/api/recurring/rules/${id}/execute`, { date })
    },

    // 获取执行历史
    getExecutions(ruleId?: number): Promise<RecurringExecution[]> {
        const params = ruleId ? { rule_id: ruleId } : {}
        return apiClient.get('/api/recurring/executions', { params })
    }
}
