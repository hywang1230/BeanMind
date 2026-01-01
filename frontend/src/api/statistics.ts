import apiClient from './client'

// 资产概览数据类型
export type AssetOverview = {
    net_assets: number          // 净资产
    total_assets: number        // 总资产
    total_liabilities: number   // 总负债
    currency: string
}

// 类别统计数据类型
export type CategoryStatistics = {
    category: string
    amount: number
    percentage: number
    count: number
}

// 月度趋势数据类型
export type MonthlyTrend = {
    month: string              // 格式: YYYY-MM
    income: number
    expense: number
    net: number
}

// 常用账户/分类数据类型
export type FrequentItem = {
    name: string               // 账户/分类名称
    count: number              // 使用次数
    last_used: string          // 最后使用日期
}

export const statisticsApi = {
    // 获取资产概览
    getAssetOverview(): Promise<AssetOverview> {
        return apiClient.get('/api/statistics/assets')
    },

    // 获取支出/收入类别统计
    getCategoryStatistics(params: {
        type: 'expense' | 'income'
        start_date?: string
        end_date?: string
        limit?: number
    }): Promise<CategoryStatistics[]> {
        return apiClient.get('/api/statistics/categories', { params })
    },

    // 获取月度趋势数据
    getMonthlyTrend(params: {
        months?: number  // 默认 6 个月
    }): Promise<MonthlyTrend[]> {
        return apiClient.get('/api/statistics/trend', { params })
    },

    // 获取常用账户/分类
    getFrequentItems(params: {
        type: 'expense' | 'income' | 'transfer' | 'account'
        days?: number      // 默认 30 天
        limit?: number     // 默认 3 个
    }): Promise<FrequentItem[]> {
        return apiClient.get('/api/statistics/frequent', { params })
    }
}
