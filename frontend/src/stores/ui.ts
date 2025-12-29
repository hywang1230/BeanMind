import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 主题模式类型
 */
export type ThemeMode = 'light' | 'dark' | 'auto'

const THEME_STORAGE_KEY = 'beanmind-theme-mode'

/**
 * 流水页面筛选条件
 */
export interface TransactionsFilters {
    typeFilter: string  // 'all' | 'expense' | 'income' | 'transfer'
    dateRange: {
        start: string
        end: string
    }
    searchKeyword?: string  // 搜索关键词（同时搜索备注和付款方）
}

/**
 * UI 状态管理 Store
 * 用于保存和恢复页面状态，确保页面导航时能回到之前的位置
 */
export const useUIStore = defineStore('ui', () => {
    // 主题模式：light（亮色）、dark（暗黑）、auto（跟随系统）
    const themeMode = ref<ThemeMode>(
        (localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode) || 'auto'
    )

    // 当前激活的 Tab ID（tab-1, tab-2, tab-3, tab-4）
    const activeTabId = ref<string>('tab-1')

    // 流水页面的滚动位置
    const transactionsScrollPosition = ref<number>(0)

    // 是否需要在返回时恢复 Tab 状态
    const shouldRestoreTab = ref<boolean>(false)

    // 流水页面的筛选条件
    const transactionsFilters = ref<TransactionsFilters>({
        typeFilter: 'all',
        dateRange: { start: '', end: '' },
        searchKeyword: ''
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

    /**
     * 设置主题模式
     */
    function setThemeMode(mode: ThemeMode) {
        themeMode.value = mode
        localStorage.setItem(THEME_STORAGE_KEY, mode)
        applyTheme(mode)
    }

    /**
     * 应用主题到 DOM
     */
    function applyTheme(mode: ThemeMode) {
        const htmlEl = document.documentElement

        // 移除所有主题相关类
        htmlEl.classList.remove('dark', 'theme-dark', 'theme-light')

        if (mode === 'auto') {
            // 跟随系统
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
            if (prefersDark) {
                htmlEl.classList.add('dark', 'theme-dark')
            } else {
                htmlEl.classList.add('theme-light')
            }
        } else if (mode === 'dark') {
            // 暗黑模式：添加 Framework7 的 dark 类和自定义 theme-dark 类
            htmlEl.classList.add('dark', 'theme-dark')
        } else {
            // 亮色模式
            htmlEl.classList.add('theme-light')
        }
    }

    /**
     * 初始化主题
     */
    function initTheme() {
        applyTheme(themeMode.value)

        // 监听系统主题变化（仅在 auto 模式下生效）
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (themeMode.value === 'auto') {
                applyTheme('auto')
            }
        })
    }

    return {
        themeMode,
        activeTabId,
        transactionsScrollPosition,
        transactionsFilters,
        shouldRestoreTab,
        transactionsNeedsRefresh,
        setThemeMode,
        initTheme,
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

