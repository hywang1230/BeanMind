<template>
  <PullToRefresh @refresh="onRefresh">
    <div class="transactions-page">
      <!-- 顶部标题 -->
      <div class="page-header">
        <h1>流水</h1>
      </div>

      <!-- 筛选器 -->
      <div class="filter-section">
        <!-- 搜索框 -->
        <div class="search-box">
          <f7-icon ios="f7:search" size="18" class="search-icon"></f7-icon>
          <input type="text" v-model="searchKeyword" placeholder="搜索备注、付款方..." @input="onSearchInput"
            @keyup.enter="applyFilters" class="search-input" />
          <f7-button v-if="searchKeyword" fill small round color="gray" @click="clearSearch" class="clear-search-btn">
            <f7-icon ios="f7:xmark" size="12"></f7-icon>
          </f7-button>
        </div>

        <f7-segmented strong tag="div" class="type-filter">
          <f7-button v-for="filter in typeFilters" :key="filter.value" :active="currentTypeFilter === filter.value"
            @click="selectTypeFilter(filter.value)">
            {{ filter.label }}
          </f7-button>
        </f7-segmented>

        <div class="date-filter-row">
          <f7-button fill small :color="hasDateFilter ? 'blue' : 'gray'" @click="openDateRangePicker"
            class="date-range-btn">
            <f7-icon ios="f7:calendar" size="16" style="margin-right: 4px;"></f7-icon>
            {{ dateRangeText }}
          </f7-button>
          <f7-button v-if="hasDateFilter" fill small color="red" @click="clearDateFilter" class="clear-date-btn">
            <f7-icon ios="f7:xmark" size="16"></f7-icon>
          </f7-button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && transactions.length === 0" class="loading-container">
        <f7-preloader></f7-preloader>
      </div>

      <!-- 空状态 -->
      <div v-else-if="transactions.length === 0" class="empty-state">
        <div class="empty-icon">📝</div>
        <div class="empty-text">暂无交易记录</div>
        <f7-button fill round @click="navigateToAdd" class="empty-action-btn">
          开始记账
        </f7-button>
      </div>

      <!-- 交易列表 -->
      <div v-else class="transactions-content" ref="scrollContent">
        <div v-for="group in groupedTransactions" :key="group.date" class="transaction-group">
          <!-- 日期分组头 -->
          <div class="date-group-header">
            <span class="date-title">{{ formatGroupDate(group.date) }}</span>
            <span class="day-summary" :class="getDaySummaryClass(group.total)">
              {{ formatDayTotal(group.total) }}
            </span>
          </div>

          <!-- 该日期的交易列表 - 独立的圆角卡片 -->
          <f7-list media-list dividers-ios strong inset class="transaction-list">
            <f7-list-item v-for="transaction in group.items" :key="transaction.id" link="#"
              @click="viewTransaction(transaction)" class="transaction-item" :class="getTransactionClass(transaction)">
              <template #media>
                <div class="transaction-icon" :class="getIconClass(transaction)">
                  <f7-icon :ios="getIcon(transaction)" size="20"></f7-icon>
                </div>
              </template>
              <template #title>
                <span class="transaction-title">{{ getCategory(transaction) }}</span>
              </template>
              <template #subtitle>
                <span class="transaction-desc">{{ getDisplayDescription(transaction) }}</span>
              </template>
              <template #after>
                <span class="transaction-amount" :class="getAmountClass(transaction)">
                  {{ formatAmount(transaction) }}
                </span>
              </template>
            </f7-list-item>
          </f7-list>
        </div>

        <!-- 加载更多指示器 -->
        <div v-if="hasMore" class="load-more-indicator" ref="loadMoreTrigger">
          <f7-preloader v-if="loadingMore"></f7-preloader>
          <span v-else class="load-more-text">上滑加载更多</span>
        </div>

        <!-- 没有更多数据 -->
        <div v-else-if="transactions.length > 0" class="no-more-data">
          <span>— 没有更多了 —</span>
        </div>
      </div>
    </div>
  </PullToRefresh>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { f7 } from 'framework7-vue'
import { useTransactionStore } from '../../stores/transaction'
import { useUIStore } from '../../stores/ui'
import { type Transaction, type TransactionsQuery, transactionsApi } from '../../api/transactions'
import PullToRefresh from '../../components/PullToRefresh.vue'

const router = useRouter()
const transactionStore = useTransactionStore()
const uiStore = useUIStore()

const loading = ref(false)
const loadingMore = ref(false)
const pageSize = 20
const loadMoreTrigger = ref<HTMLElement | null>(null)

// 汇率数据（货币 -> CNY 的汇率）
const exchangeRates = ref<Record<string, number>>({ CNY: 1 })

// 货币符号映射
const currencySymbols: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  HKD: 'HK$',
  TWD: 'NT$',
  KRW: '₩',
  SGD: 'S$',
  AUD: 'A$',
  CAD: 'C$',
}

// 获取货币符号
function getCurrencySymbol(currency: string): string {
  return currencySymbols[currency] || currency + ' '
}

const typeFilters = [
  { value: 'all', label: '全部' },
  { value: 'expense', label: '支出' },
  { value: 'income', label: '收入' },
  { value: 'transfer', label: '转账' }
]

const currentTypeFilter = ref<string>('all')
const dateRange = ref({
  start: '',
  end: ''
})
const searchKeyword = ref<string>('')
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const transactions = computed(() => transactionStore.transactions)
const total = computed(() => transactionStore.total)

const hasMore = computed(() => {
  return transactions.value.length < total.value
})

const hasDateFilter = computed(() => {
  return dateRange.value.start !== '' || dateRange.value.end !== ''
})

const dateRangeText = computed(() => {
  if (dateRange.value.start && dateRange.value.end) {
    return `${formatShortDate(dateRange.value.start)} - ${formatShortDate(dateRange.value.end)}`
  } else if (dateRange.value.start) {
    return `${formatShortDate(dateRange.value.start)} 起`
  } else if (dateRange.value.end) {
    return `至 ${formatShortDate(dateRange.value.end)}`
  }
  return '选择日期范围'
})

function formatShortDate(dateStr: string): string {
  const parts = dateStr.split('-')
  return `${parts[1]}/${parts[2]}`
}

// 按日期分组交易
interface TransactionGroup {
  date: string
  items: Transaction[]
  total: number
}

const groupedTransactions = computed<TransactionGroup[]>(() => {
  const groups: Record<string, TransactionGroup> = {}

  for (const transaction of transactions.value) {
    const date = transaction.date
    if (!groups[date]) {
      groups[date] = { date, items: [], total: 0 }
    }
    groups[date].items.push(transaction)

    // 计算当日总额
    const amount = getTransactionAmount(transaction)
    groups[date].total += amount
  }

  // 对每个日期分组内的流水按 lineno 倒序排列（新的记账排在前面）
  for (const group of Object.values(groups)) {
    group.items.sort((a, b) => {
      const linenoA = a.meta?.lineno ?? Infinity  // 如果没有 lineno，排在最前面
      const linenoB = b.meta?.lineno ?? Infinity
      return linenoB - linenoA  // 倒序：行号大的排前面
    })
  }

  // 按日期降序排列
  return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

// 辅助函数：获取用于显示的金额值（正负号），不进行汇率转换
function getDisplayAmountValue(transaction: Transaction): number {
  if (transaction.postings.length === 0) return 0

  let totalAmount = 0
  let hasCategory = false

  for (const posting of transaction.postings) {
    const amount = Number(posting.amount)
    if (posting.account.startsWith('Income:')) {
      // Beancount 中 Income 账户：负数表示收入（盈利）
      totalAmount += -amount  // 取反，负数变正数表示收入
      hasCategory = true
    } else if (posting.account.startsWith('Expenses:')) {
      totalAmount += -amount  // 取反，正数变负数表示支出
      hasCategory = true
    }
  }

  // 如果没有分类账户（转账），取负数一方的金额汇总，然后取相反数
  if (!hasCategory && transaction.postings.length > 0) {
    let negativeTotal = 0
    for (const posting of transaction.postings) {
      const amount = Number(posting.amount)
      if (amount < 0) {
        negativeTotal += amount  // 累加负数金额
      }
    }
    // 取相反数作为显示金额（转账不参与日汇总，返回0用于汇总，但显示时用正数）
    return -negativeTotal
  }

  return totalAmount
}

// 获取交易的主要货币（用于显示）
function getTransactionCurrency(transaction: Transaction): string {
  if (transaction.postings.length === 0) return 'CNY'

  // 优先获取分类账户（Expenses/Income）的货币
  for (const posting of transaction.postings) {
    if (posting.account.startsWith('Expenses:') || posting.account.startsWith('Income:')) {
      return posting.currency || 'CNY'
    }
  }

  // 如果没有分类账户，取第一个 posting 的货币
  return transaction.postings[0]?.currency || 'CNY'
}

// 获取用于日汇总的金额（已转换为 CNY）
function getTransactionAmountInCNY(transaction: Transaction): number {
  if (transaction.postings.length === 0) return 0

  // 日汇总：只计算收入和支出，转账不参与
  if (transaction.transaction_type === 'transfer') {
    return 0
  }

  let totalAmountInCNY = 0

  for (const posting of transaction.postings) {
    const amount = Number(posting.amount)
    const currency = posting.currency || 'CNY'
    const rate = exchangeRates.value[currency] || 1

    if (posting.account.startsWith('Income:')) {
      // Beancount 中 Income 账户：负数表示收入（盈利）
      totalAmountInCNY += -amount * rate  // 转换为 CNY
    } else if (posting.account.startsWith('Expenses:')) {
      totalAmountInCNY += -amount * rate  // 转换为 CNY
    }
  }

  return totalAmountInCNY
}

function getTransactionAmount(transaction: Transaction): number {
  // 日汇总：只计算收入和支出，转账不参与，使用 CNY 汇总
  return getTransactionAmountInCNY(transaction)
}


// 日期范围选择器
let dateRangeCalendar: any = null

function openDateRangePicker() {
  // 销毁旧日历以确保新配置生效
  if (dateRangeCalendar) {
    dateRangeCalendar.destroy()
    dateRangeCalendar = null
  }

  dateRangeCalendar = f7.calendar.create({
    openIn: 'customModal',
    rangePicker: true,
    header: true,
    headerPlaceholder: '选择日期范围',
    toolbar: true,
    toolbarCloseText: '完成',
    monthPicker: true,
    yearPicker: true,
    closeByOutsideClick: true,
    cssClass: 'date-range-calendar',
    on: {
      change: function (calendar: any, value: unknown) {
        const values = value as Date[]
        // 当选择了两个日期（完整的日期范围）时，自动关闭日历
        if (values && values.length === 2 && values[0] && values[1]) {
          dateRange.value.start = formatDateValue(values[0])
          dateRange.value.end = formatDateValue(values[1])
          calendar.close()
          applyFilters()
        }
      }
    }
  })

  // 设置初始值
  if (dateRange.value.start && dateRange.value.end) {
    dateRangeCalendar.setValue([
      new Date(dateRange.value.start),
      new Date(dateRange.value.end)
    ])
  }

  dateRangeCalendar.open()
}

function formatDateValue(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function selectTypeFilter(filter: string) {
  if (currentTypeFilter.value === filter) return
  currentTypeFilter.value = filter
  loadTransactions(true)
}

function applyFilters() {
  loadTransactions(true)
}

function clearDateFilter() {
  dateRange.value = { start: '', end: '' }
  loadTransactions(true)
}

function onSearchInput() {
  // 防抖处理
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    loadTransactions(true)
  }, 300)
}

function clearSearch() {
  searchKeyword.value = ''
  loadTransactions(true)
}

async function loadTransactions(reset: boolean = false) {
  if (reset) {
    loading.value = true
  } else {
    loadingMore.value = true
  }

  try {
    const query: TransactionsQuery = {
      limit: pageSize,
      offset: reset ? 0 : transactions.value.length
    }

    if (currentTypeFilter.value !== 'all') {
      query.transaction_type = currentTypeFilter.value as 'expense' | 'income' | 'transfer'
    }

    if (dateRange.value.start) {
      query.start_date = dateRange.value.start
    }

    if (dateRange.value.end) {
      query.end_date = dateRange.value.end
    }

    // 搜索关键词（同时搜索备注和付款方）
    if (searchKeyword.value.trim()) {
      query.description = searchKeyword.value.trim()
    }

    await transactionStore.fetchTransactions(query, !reset)
  } finally {
    loading.value = false
    loadingMore.value = false

    // 重新设置观察器
    if (reset) {
      await nextTick()
      setupIntersectionObserver()
    }
  }
}

// 使用 IntersectionObserver 实现无限滚动
let observer: IntersectionObserver | null = null

function setupIntersectionObserver() {
  // 清除旧的 observer
  if (observer) {
    observer.disconnect()
  }

  // 创建新的 observer
  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && hasMore.value && !loadingMore.value && !loading.value) {
        loadMore()
      }
    })
  }, {
    root: null, // 使用视口作为 root，兼容 Framework7 tab 嵌套
    rootMargin: '200px',
    threshold: 0
  })

  // 监听加载更多触发器
  if (loadMoreTrigger.value) {
    observer.observe(loadMoreTrigger.value)
  }
}

// 监听 hasMore 变化，更新 observer
watch(hasMore, async (newVal) => {
  if (newVal) {
    await nextTick()
    setupIntersectionObserver()
  }
})

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return

  loadingMore.value = true

  try {
    const query: TransactionsQuery = {
      limit: pageSize,
      offset: transactions.value.length
    }

    if (currentTypeFilter.value !== 'all') {
      query.transaction_type = currentTypeFilter.value as 'expense' | 'income' | 'transfer'
    }
    if (dateRange.value.start) {
      query.start_date = dateRange.value.start
    }
    if (dateRange.value.end) {
      query.end_date = dateRange.value.end
    }
    // 搜索关键词
    if (searchKeyword.value.trim()) {
      query.description = searchKeyword.value.trim()
    }

    await transactionStore.fetchTransactions(query, true) // append mode
  } finally {
    loadingMore.value = false
  }
}

const TRANSACTIONS_TAB_ID = 'tab-2'

function navigateToAdd() {
  uiStore.markForTabRestore()
  router.push('/transactions/add')
}

function viewTransaction(transaction: Transaction) {
  // 保存当前滚动位置
  saveScrollPosition()
  // 保存筛选条件
  saveFilters()
  // 标记当前在流水 Tab，需要在返回时恢复
  uiStore.setActiveTab(TRANSACTIONS_TAB_ID)
  uiStore.markForTabRestore()
  router.push(`/transactions/${transaction.id}`)
}

/**
 * 获取滚动容器（F7 Tab 的 page-content）
 */
function getScrollContainer(): HTMLElement | null {
  // F7 Tab 结构: f7-tab.page-content > transactions-page > transactions-content
  // 滚动发生在 f7-tab.page-content 上
  const tabContent = document.querySelector(`#${TRANSACTIONS_TAB_ID}.page-content`) as HTMLElement
  return tabContent
}

/**
 * 保存当前滚动位置
 */
function saveScrollPosition() {
  const container = getScrollContainer()
  if (container) {
    const position = container.scrollTop
    uiStore.saveTransactionsScrollPosition(position)
  }
}

/**
 * 恢复滚动位置
 */
function restoreScrollPosition() {
  const savedPosition = uiStore.getAndClearTransactionsScrollPosition()
  if (savedPosition > 0) {
    // 使用多次延迟确保 DOM 完全就绪
    nextTick(() => {
      setTimeout(() => {
        const container = getScrollContainer()
        if (container) {
          container.scrollTop = savedPosition
        }
      }, 100)
    })
  }
}

/**
 * 保存筛选条件
 */
function saveFilters() {
  uiStore.saveTransactionsFilters({
    typeFilter: currentTypeFilter.value,
    dateRange: { ...dateRange.value },
    searchKeyword: searchKeyword.value
  })
}

/**
 * 恢复筛选条件
 */
function restoreFilters() {
  const filters = uiStore.getTransactionsFilters()
  currentTypeFilter.value = filters.typeFilter
  dateRange.value = { ...filters.dateRange }
  searchKeyword.value = filters.searchKeyword || ''
}

function getTransactionClass(transaction: Transaction): string {
  const type = transaction.transaction_type
  if (type === 'income') return 'income-item'
  if (type === 'expense') return 'expense-item'
  if (type === 'transfer') return 'transfer-item'
  return ''
}

function getIcon(transaction: Transaction): string {
  const type = transaction.transaction_type
  if (type === 'income') return 'f7:arrow_down_circle'
  if (type === 'expense') return 'f7:arrow_up_circle'
  if (type === 'transfer') return 'f7:arrow_right_arrow_left_circle'
  return 'f7:doc_text'
}

function getIconClass(transaction: Transaction): string {
  const type = transaction.transaction_type
  if (type === 'income') return 'income-icon'
  if (type === 'expense') return 'expense-icon'
  if (type === 'transfer') return 'transfer-icon'
  return ''
}

function getDisplayDescription(transaction: Transaction): string {
  const parts: string[] = []
  if (transaction.payee) parts.push(transaction.payee)
  if (transaction.description) parts.push(transaction.description)
  return parts.join(' - ') || ''
}

function getCategory(transaction: Transaction): string {
  if (transaction.postings.length === 0) return '未分类'

  // 提取所有非资产/负债账户（即分类账户）的名称
  const categories: string[] = []

  for (const posting of transaction.postings) {
    const account = posting.account
    // 只显示支出和收入分类，跳过资产和负债账户
    if (account.startsWith('Expenses:') || account.startsWith('Income:')) {
      const parts = account.split(':')
      if (parts.length >= 2) {
        categories.push(parts[parts.length - 1]!)
      } else {
        categories.push(parts[0]!)
      }
    }
  }

  if (categories.length === 0) {
    // 如果没有找到分类账户，使用第一个账户
    const account = transaction.postings[0]!.account
    const parts = account.split(':')
    return parts.length >= 2 ? parts[parts.length - 1]! : parts[0]!
  }

  return categories.join(', ')
}

function getAmountClass(transaction: Transaction): string {
  if (transaction.postings.length === 0) return ''

  // 转账用蓝色
  if (transaction.transaction_type === 'transfer') {
    return 'neutral'
  }

  // 收入/支出根据金额正负决定颜色
  const amount = getDisplayAmountValue(transaction)
  if (amount > 0) return 'positive'
  if (amount < 0) return 'negative'
  return 'neutral'
}

function formatAmount(transaction: Transaction): string {
  if (transaction.postings.length === 0) return '¥0.00'

  // 获取交易的主要币种
  const currency = getTransactionCurrency(transaction)
  const symbol = getCurrencySymbol(currency)

  // 使用统一的金额计算逻辑
  const amount = getDisplayAmountValue(transaction)
  const displayAmount = Math.abs(amount)

  // 不显示 +/- 符号，只用颜色区分
  return `${symbol}${displayAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatGroupDate(dateStr: string): string {
  const date = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const month = date.getMonth() + 1
  const day = date.getDate()
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekDay = weekDays[date.getDay()]

  if (dateStr === formatDateValue(today)) {
    return `今天 ${month}月${day}日`
  } else if (dateStr === formatDateValue(yesterday)) {
    return `昨天 ${month}月${day}日`
  }

  return `${month}月${day}日 ${weekDay}`
}

function getDaySummaryClass(total: number): string {
  if (total > 0) return 'positive'
  if (total < 0) return 'negative'
  return ''
}

function formatDayTotal(total: number): string {
  if (total === 0) return ''
  // 不显示 +/- 符号，只用颜色区分
  return `¥${Math.abs(total).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// 加载汇率数据
async function loadExchangeRates() {
  try {
    const rates = await transactionsApi.getExchangeRates()
    exchangeRates.value = { CNY: 1, ...rates }
  } catch (error) {
    console.error('加载汇率失败:', error)
    // 保持默认汇率
  }
}

onMounted(async () => {
  // 检查是否需要刷新数据（在删除、新增、编辑操作后）
  const needsRefresh = uiStore.checkAndClearTransactionsRefresh()

  if (needsRefresh) {
    // 恢复筛选条件
    restoreFilters()
    // 并行加载汇率和交易数据（性能优化：减少首屏渲染阻塞）
    await Promise.all([
      loadExchangeRates(),
      loadTransactions(true)
    ])
    // 不恢复滚动位置，因为数据已经变化了
  } else if (transactionStore.transactions.length === 0) {
    // 首次加载：并行加载汇率和交易数据
    await Promise.all([
      loadExchangeRates(),
      loadTransactions(true)
    ])
  } else {
    // 正常返回，恢复筛选条件和滚动位置
    restoreFilters()
    restoreScrollPosition()
    // 后台刷新汇率（不阻塞）
    loadExchangeRates()
    // 重新设置 IntersectionObserver（返回页面时原来的 observer 已失效）
    await nextTick()
    setupIntersectionObserver()
  }
})

// 暴露方法给父组件（如果需要的话）
defineExpose({
  restoreScrollPosition
})

// 下拉刷新处理
async function onRefresh(done: () => void) {
  try {
    // 重置并重新加载交易数据
    await loadTransactions(true)
  } finally {
    done()
  }
}

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
  if (dateRangeCalendar) {
    dateRangeCalendar.destroy()
  }
})
</script>


<style scoped>
.transactions-page {
  min-height: 100vh;
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  transition: background-color 0.3s;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  position: sticky;
  top: 0;
  background: var(--bg-primary);
  z-index: 10;
  transition: background-color 0.3s;
}

.page-header h1 {
  font-size: 34px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.4px;
}

/* 筛选区域 */
.filter-section {
  padding: 0 16px 12px;
  background: var(--bg-primary);
  transition: background-color 0.3s;
}

/* 搜索框 */
.search-box {
  display: flex;
  align-items: center;
  background: var(--bg-secondary);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition: background-color 0.3s;
}

.search-icon {
  color: #8e8e93;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  padding: 0 8px;
  background: transparent;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: #8e8e93;
}

.clear-search-btn {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  min-width: 20px;
  padding: 0;
  --f7-button-bg-color: rgba(142, 142, 147, 0.12);
}

.type-filter {
  margin-bottom: 12px;
}

.date-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-range-btn {
  flex: 1;
}

.clear-date-btn {
  flex-shrink: 0;
  width: 36px;
  padding: 0;
}

/* 加载状态 */
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: #8e8e93;
  margin-bottom: 24px;
}

.empty-action-btn {
  display: inline-block;
}

/* 交易内容区 */
.transactions-content {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 16px 80px;
}

.transaction-list {
  margin: 0;
  --f7-list-inset-side-margin: 0;
  --f7-list-inset-border-radius: 12px;
  border-radius: 12px;
  overflow: hidden;
}

/* 交易分组 */
.transaction-group {
  margin-bottom: 16px;
}

/* 日期分组头 */
.date-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
}

.date-title {
  font-size: 13px;
  color: #8e8e93;
  font-weight: 600;
  text-transform: uppercase;
}

.day-summary {
  font-size: 13px;
  font-weight: 600;
}

.day-summary.positive {
  color: var(--ios-green);
}

.day-summary.negative {
  color: var(--ios-red);
}

/* 交易项 */
.transaction-item {
  --f7-list-item-padding-horizontal: 16px;
  background: var(--bg-secondary);
  /* 确保列表项背景正确 */
}

.transaction-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.transaction-icon.expense-icon {
  background: rgba(255, 59, 48, 0.12);
  color: var(--ios-red);
}

.transaction-icon.income-icon {
  background: rgba(52, 199, 89, 0.12);
  color: var(--ios-green);
}

.transaction-icon.transfer-icon {
  background: rgba(0, 122, 255, 0.12);
  color: var(--ios-blue);
}

.transaction-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.transaction-desc {
  font-size: 13px;
  color: #8e8e93;
}

.transaction-amount {
  font-size: 17px;
  font-weight: 600;
}

.transaction-amount.positive {
  color: var(--ios-green);
}

.transaction-amount.negative {
  color: var(--ios-red);
}

.transaction-amount.neutral {
  color: var(--ios-blue);
}

/* 加载更多 */
.load-more-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  min-height: 60px;
}

.load-more-text {
  font-size: 13px;
  color: #8e8e93;
}

.no-more-data {
  text-align: center;
  padding: 20px;
  color: #8e8e93;
  font-size: 13px;
}
</style>

<!-- 全局样式，用于隐藏日历 header 中的关闭按钮 -->
<style>
.date-range-calendar .calendar-header .calendar-header-close {
  display: none !important;
}
</style>
