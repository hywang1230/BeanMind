import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 流水页面筛选条件
 */
export interface TransactionsFilters {
    typeFilter: string  // 'all' | 'expense' | 'income' | 'transfer'
    dateRange: {
        start: string
        end: string
    }
}

/**
 * UI 状态管理 Store
 * 用于保存和恢复页面状态，确保页面导航时能回到之前的位置
 */
export const useUIStore = defineStore('ui', () => {
    // 当前激活的 Tab ID（tab-1, tab-2, tab-3, tab-4）
    const activeTabId = ref<string>('tab-1')

    // 流水页面的滚动位置
    const transactionsScrollPosition = ref<number>(0)

    // 是否需要在返回时恢复 Tab 状态
    const shouldRestoreTab = ref<boolean>(false)

    // 流水页面的筛选条件
    const transactionsFilters = ref<TransactionsFilters>({
        typeFilter: 'all',
        dateRange: { start: '', end: '' }
    })

    // 是否需要刷新交易列表数据（在删除、新增、编辑操作后）
    const transactionsNeedsRefresh = ref<boolean>(false)

    /**
     * 设置当前激活的 Tab
     */
    function setActiveTab(tabId: string) {
        activeTabId.value = tabId
    }

    /**
     * 保存流水页面滚动位置
     */
    function saveTransactionsScrollPosition(position: number) {
        transactionsScrollPosition.value = position
    }

    /**
     * 获取流水页面滚动位置
     */
    function getAndClearTransactionsScrollPosition(): number {
        const position = transactionsScrollPosition.value
        return position
    }

    /**
     * 保存流水页面筛选条件
     */
    function saveTransactionsFilters(filters: TransactionsFilters) {
        transactionsFilters.value = { ...filters }
    }

    /**
     * 获取流水页面筛选条件
     */
    function getTransactionsFilters(): TransactionsFilters {
        return { ...transactionsFilters.value }
    }

    /**
     * 标记需要在返回时恢复 Tab
     */
    function markForTabRestore() {
        shouldRestoreTab.value = true
    }

    /**
     * 清除恢复标记
     */
    function clearTabRestoreFlag(): boolean {
        const shouldRestore = shouldRestoreTab.value
        shouldRestoreTab.value = false
        return shouldRestore
    }

    /**
     * 标记交易列表需要刷新
     */
    function markTransactionsNeedsRefresh() {
        transactionsNeedsRefresh.value = true
    }

    /**
     * 检查并清除交易列表刷新标记
     */
    function checkAndClearTransactionsRefresh(): boolean {
        const needsRefresh = transactionsNeedsRefresh.value
        transactionsNeedsRefresh.value = false
        return needsRefresh
    }

    return {
        activeTabId,
        transactionsScrollPosition,
        transactionsFilters,
        shouldRestoreTab,
        transactionsNeedsRefresh,
        setActiveTab,
        saveTransactionsScrollPosition,
        getAndClearTransactionsScrollPosition,
        saveTransactionsFilters,
        getTransactionsFilters,
        markForTabRestore,
        clearTabRestoreFlag,
        markTransactionsNeedsRefresh,
        checkAndClearTransactionsRefresh
    }
})

