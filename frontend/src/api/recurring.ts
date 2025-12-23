import apiClient from './client'

export type RecurringRule = {
    id: number | string
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
    payee?: string
    postings: {
        account: string
        amount: number
        currency: string
    }[]
    tags?: string[]
}

export type RecurringExecution = {
    id: number | string
    rule_id: number | string
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
    getRule(id: number | string): Promise<RecurringRule> {
        return apiClient.get(`/api/recurring/rules/${id}`)
    },

    // 更新规则
    updateRule(id: number | string, data: Partial<CreateRecurringRuleRequest>): Promise<RecurringRule> {
        return apiClient.put(`/api/recurring/rules/${id}`, data)
    },

    // 删除规则
    deleteRule(id: number | string): Promise<void> {
        return apiClient.delete(`/api/recurring/rules/${id}`)
    },

    // 手动执行规则
    executeRule(id: number | string, date: string): Promise<RecurringExecution> {
        return apiClient.post(`/api/recurring/rules/${id}/execute`, { date })
    },

    // 获取执行历史
    getExecutions(ruleId?: number | string): Promise<RecurringExecution[]> {
        const params = ruleId ? { rule_id: ruleId } : {}
        return apiClient.get('/api/recurring/executions', { params })
    }
}
