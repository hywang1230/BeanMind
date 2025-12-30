/**
 * 统计数据缓存 Store
 * 
 * 为首页统计数据提供缓存层，避免频繁重复请求 API。
 * 使用 Pinia 管理状态，支持缓存过期和强制刷新。
 */
import { defineStore } from 'pinia'
import { statisticsApi, type AssetOverview, type CategoryStatistics, type MonthlyTrend } from '../api/statistics'

// 缓存过期时间（毫秒）
const CACHE_EXPIRY_MS = 60 * 1000  // 1 分钟

interface StatisticsState {
    // 资产概览
    assetOverview: AssetOverview | null
    // 类别统计（支出 Top N）
    categoryStats: CategoryStatistics[]
    // 月度趋势
    monthlyTrend: MonthlyTrend[]
    // 最后更新时间戳
    lastUpdated: number | null
    // 是否正在加载
    loading: boolean
    // 错误信息
    error: string | null
}

export const useStatisticsStore = defineStore('statistics', {
    state: (): StatisticsState => ({
        assetOverview: null,
        categoryStats: [],
        monthlyTrend: [],
        lastUpdated: null,
        loading: false,
        error: null
    }),

    getters: {
        /**
         * 检查缓存是否有效
         */
        isCacheValid(): boolean {
            if (!this.lastUpdated) return false
            return Date.now() - this.lastUpdated < CACHE_EXPIRY_MS
        },

        /**
         * 获取净资产（快速访问）
         */
        netAssets(): number {
            return this.assetOverview?.net_assets ?? 0
        },

        /**
         * 获取本月收入（从趋势数据最后一个月）
         */
        currentMonthIncome(): number {
            if (this.monthlyTrend.length === 0) return 0
            return this.monthlyTrend[this.monthlyTrend.length - 1]?.income ?? 0
        },

        /**
         * 获取本月支出（从趋势数据最后一个月）
         */
        currentMonthExpense(): number {
            if (this.monthlyTrend.length === 0) return 0
            return this.monthlyTrend[this.monthlyTrend.length - 1]?.expense ?? 0
        },

        /**
         * 获取本月结余
         */
        currentMonthNet(): number {
            if (this.monthlyTrend.length === 0) return 0
            return this.monthlyTrend[this.monthlyTrend.length - 1]?.net ?? 0
        }
    },

    actions: {
        /**
         * 获取首页所需的所有统计数据
         * 
         * @param force 是否强制刷新（忽略缓存）
         * @returns 统计数据对象
         */
        async fetchDashboardData(force = false) {
            // 如果缓存有效且不强制刷新，直接返回
            if (!force && this.isCacheValid) {
                return {
                    assets: this.assetOverview,
                    categories: this.categoryStats,
                    trend: this.monthlyTrend
                }
            }

            this.loading = true
            this.error = null

            try {
                // 并行请求所有统计数据
                const [assets, categories, trend] = await Promise.all([
                    statisticsApi.getAssetOverview().catch(() => ({
                        net_assets: 0, total_assets: 0, total_liabilities: 0, currency: 'CNY'
                    })),
                    statisticsApi.getCategoryStatistics({ type: 'expense', limit: 3 }).catch(() => []),
                    statisticsApi.getMonthlyTrend({ months: 6 }).catch(() => [])
                ])

                // 更新状态
                this.assetOverview = assets
                this.categoryStats = categories
                this.monthlyTrend = trend
                this.lastUpdated = Date.now()

                return { assets, categories, trend }
            } catch (error) {
                this.error = error instanceof Error ? error.message : '加载失败'
                console.error('Failed to load dashboard data:', error)
                throw error
            } finally {
                this.loading = false
            }
        },

        /**
         * 使缓存失效
         * 
         * 在添加/修改/删除交易后调用，确保下次加载首页时刷新数据
         */
        invalidateCache() {
            this.lastUpdated = null
        },

        /**
         * 清除所有数据
         */
        clearData() {
            this.assetOverview = null
            this.categoryStats = []
            this.monthlyTrend = []
            this.lastUpdated = null
            this.error = null
        }
    }
})
