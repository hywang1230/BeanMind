<template>
  <div class="transactions-page">
    <!-- 顶部标题 -->
    <div class="page-header">
      <h1>流水</h1>
    </div>

    <!-- 筛选器 -->
    <div class="filter-section">
      <f7-segmented strong tag="div" class="type-filter">
        <f7-button 
          v-for="filter in typeFilters" 
          :key="filter.value"
          :active="currentTypeFilter === filter.value"
          @click="selectTypeFilter(filter.value)"
        >
          {{ filter.label }}
        </f7-button>
      </f7-segmented>
      
      <div class="date-filter-row">
        <f7-button 
          fill 
          small 
          :color="hasDateFilter ? 'blue' : 'gray'" 
          @click="openDateRangePicker"
          class="date-range-btn"
        >
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
          <f7-list-item
            v-for="transaction in group.items"
            :key="transaction.id"
            link="#"
            @click="viewTransaction(transaction)"
            class="transaction-item"
            :class="getTransactionClass(transaction)"
          >
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
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { f7 } from 'framework7-vue'
import { useTransactionStore } from '../../stores/transaction'
import { useUIStore } from '../../stores/ui'
import { type Transaction, type TransactionsQuery } from '../../api/transactions'

const router = useRouter()
const transactionStore = useTransactionStore()
const uiStore = useUIStore()

const loading = ref(false)
const loadingMore = ref(false)
const pageSize = 20
const loadMoreTrigger = ref<HTMLElement | null>(null)

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
  
  // 按日期降序排列
  return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

function getTransactionAmount(transaction: Transaction): number {
  if (transaction.postings.length === 0) return 0
  const posting = transaction.postings[0]!
  const amount = Number(posting.amount)
  
  // 支出为负，收入为正
  if (posting.account.startsWith('Expenses')) {
    return -Math.abs(amount)
  } else if (posting.account.startsWith('Income')) {
    return Math.abs(amount)
  }
  return 0 // 转账不计入
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
    
    await transactionStore.fetchTransactions(query, true) // append mode
  } finally {
    loadingMore.value = false
  }
}

function navigateToAdd() {
  router.push('/transactions/add')
}

function viewTransaction(transaction: Transaction) {
  // 保存当前滚动位置
  saveScrollPosition()
  // 保存筛选条件
  saveFilters()
  // 标记当前在流水 Tab，需要在返回时恢复
  uiStore.setActiveTab('tab-2')
  uiStore.markForTabRestore()
  router.push(`/transactions/${transaction.id}`)
}

/**
 * 获取滚动容器（F7 Tab 的 page-content）
 */
function getScrollContainer(): HTMLElement | null {
  // F7 Tab 结构: f7-tab.page-content > transactions-page > transactions-content
  // 滚动发生在 f7-tab.page-content 上
  const tabContent = document.querySelector('#tab-2.page-content') as HTMLElement
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
    dateRange: { ...dateRange.value }
  })
}

/**
 * 恢复筛选条件
 */
function restoreFilters() {
  const filters = uiStore.getTransactionsFilters()
  currentTypeFilter.value = filters.typeFilter
  dateRange.value = { ...filters.dateRange }
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
  
  const account = transaction.postings[0]!.account
  const parts = account.split(':')
  
  if (parts.length >= 2) {
    return parts[parts.length - 1]!
  }
  
  return parts[0]!
}

function getAmountClass(transaction: Transaction): string {
  if (transaction.postings.length === 0) return ''
  
  const account = transaction.postings[0]!.account
  if (account.startsWith('Income')) return 'positive'
  if (account.startsWith('Expenses')) return 'negative'
  return 'neutral'
}

function formatAmount(transaction: Transaction): string {
  if (transaction.postings.length === 0) return '¥0.00'
  
  const posting = transaction.postings[0]!
  const amount = Math.abs(Number(posting.amount))
  const sign = posting.account.startsWith('Income') ? '+' : 
               posting.account.startsWith('Expenses') ? '-' : ''
  
  return `${sign}¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
  const sign = total > 0 ? '+' : ''
  return `${sign}¥${total.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

onMounted(async () => {
  // 只有在 store 中没有数据时才加载（避免返回时重复加载）
  if (transactionStore.transactions.length === 0) {
    await loadTransactions(true)
  } else {
    // 恢复筛选条件
    restoreFilters()
    // 恢复滚动位置
    restoreScrollPosition()
    // 重新设置 IntersectionObserver（返回页面时原来的 observer 已失效）
    await nextTick()
    setupIntersectionObserver()
  }
})

// 暴露方法给父组件（如果需要的话）
defineExpose({
  restoreScrollPosition
})

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
  background: #f2f2f7;
  display: flex;
  flex-direction: column;
}

.page-header {
  padding: 12px 16px 8px;
  position: sticky;
  top: 0;
  background: #f2f2f7;
  z-index: 10;
}

.page-header h1 {
  font-size: 34px;
  font-weight: 700;
  color: #000;
  margin: 0;
  letter-spacing: -0.4px;
}

/* 筛选区域 */
.filter-section {
  padding: 0 16px 12px;
  background: #f2f2f7;
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
  color: #34c759;
}

.day-summary.negative {
  color: #ff3b30;
}

/* 交易项 */
.transaction-item {
  --f7-list-item-padding-horizontal: 16px;
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
  color: #ff3b30;
}

.transaction-icon.income-icon {
  background: rgba(52, 199, 89, 0.12);
  color: #34c759;
}

.transaction-icon.transfer-icon {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.transaction-title {
  font-size: 16px;
  font-weight: 500;
  color: #000;
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
  color: #34c759;
}

.transaction-amount.negative {
  color: #ff3b30;
}

.transaction-amount.neutral {
  color: #007aff;
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

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .transactions-page {
    background: #000;
  }
  
  .page-header {
    background: #000;
  }
  
  .page-header h1 {
    color: #fff;
  }
  
  .filter-section {
    background: #000;
  }
  
  .date-group-header {
    background: #000 !important;
  }
  
  .transaction-title {
    color: #fff;
  }
  
  .transaction-icon.expense-icon {
    background: rgba(255, 69, 58, 0.18);
    color: #ff453a;
  }
  
  .transaction-icon.income-icon {
    background: rgba(48, 209, 88, 0.18);
    color: #30d158;
  }
  
  .transaction-icon.transfer-icon {
    background: rgba(10, 132, 255, 0.18);
    color: #0a84ff;
  }
  
  .transaction-amount.positive {
    color: #30d158;
  }
  
  .transaction-amount.negative {
    color: #ff453a;
  }
  
  .transaction-amount.neutral {
    color: #0a84ff;
  }
}
</style>

<!-- 全局样式，用于隐藏日历 header 中的关闭按钮 -->
<style>
.date-range-calendar .calendar-header .calendar-header-close {
  display: none !important;
}
</style>
