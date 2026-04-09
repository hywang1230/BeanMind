<template>
  <f7-page name="income-statement">
    <f7-navbar title="利润表">
      <template #left>
        <f7-link @click="goBack">
          <f7-icon f7="chevron_left"></f7-icon>
          <span></span>
        </f7-link>
      </template>
      <template #right>
        <f7-link @click="openAIContext">
          <f7-icon f7="sparkles"></f7-icon>
        </f7-link>
      </template>
    </f7-navbar>

    <div class="income-statement-content">
      <!-- 日期范围选择器 -->
      <div class="date-range-section" @click="openDateRangePicker">
        <div class="date-range-display">
          <span class="date-text">{{ formatDisplayDate(startDate || '') }}</span>
          <span class="date-separator">至</span>
          <span class="date-text">{{ formatDisplayDate(endDate || '') }}</span>
        </div>
        <f7-icon f7="calendar" size="18" class="date-icon"></f7-icon>
      </div>

      <!-- 快捷日期选择 -->
      <div class="quick-date-section">
        <button v-for="preset in datePresets" :key="preset.label" class="quick-date-btn"
          :class="{ active: isPresetActive(preset) }" @click="applyPreset(preset)">
          {{ preset.label }}
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">加载中...</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-container">
        <p class="error-text">{{ error }}</p>
        <button @click="loadIncomeStatement()" class="retry-btn">重试</button>
      </div>

      <!-- 报表内容 -->
      <div v-else-if="data" class="report-body">
        <!-- 汇总卡片 -->
        <div class="summary-card">
          <div class="summary-row main-row">
            <div class="summary-label">净利润</div>
            <div class="summary-value"
              :class="{ negative: data.net_profit_cny < 0, positive: data.net_profit_cny >= 0 }">
              {{ data.net_profit_cny >= 0 ? '+' : '' }}{{ formatCurrency(data.net_profit_cny) }}
            </div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-details">
            <div class="summary-item">
              <span class="item-label">总收入</span>
              <span class="item-value income">+{{ formatCurrency(data.total_income_cny) }}</span>
            </div>
            <div class="summary-item">
              <span class="item-label">总支出</span>
              <span class="item-value expense">-{{ formatCurrency(data.total_expenses_cny) }}</span>
            </div>
          </div>
        </div>

        <!-- 收入分析图 -->
        <div v-if="data.income.items.length > 0" class="chart-card">
          <div class="card-header">收入构成</div>
          <div class="pie-chart-container">
            <div class="pie-legend">
              <div v-for="(item, index) in topIncomeItems" :key="item.account" class="legend-item">
                <span class="legend-color" :style="{ background: incomeColors[index % incomeColors.length] }"></span>
                <span class="legend-name">{{ item.display_name }}</span>
                <span class="legend-value">{{ item.percentage.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 支出分析图 -->
        <div v-if="data.expenses.items.length > 0" class="chart-card">
          <div class="card-header">支出构成</div>
          <div class="pie-chart-container">
            <div class="pie-legend">
              <div v-for="(item, index) in topExpenseItems" :key="item.account" class="legend-item">
                <span class="legend-color" :style="{ background: expenseColors[index % expenseColors.length] }"></span>
                <span class="legend-name">{{ item.display_name }}</span>
                <span class="legend-value">{{ item.percentage.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 收入类 -->
        <div class="category-section">
          <div class="category-header">
            <div class="category-title">
              <span class="category-icon income">💰</span>
              <span>收入</span>
            </div>
            <div class="category-total income">+{{ formatCurrency(data.income.total_cny) }}</div>
          </div>
          <div class="items-list">
            <IncomeExpenseTreeItem v-for="item in sortedIncomeItems" :key="item.account" :item="item" type="income"
              :default-expanded="false" :expanded-accounts="expandedAccounts" @click-account="handleAccountClick"
              @toggle-expand="handleToggleExpand" />
          </div>
          <div v-if="data.income.items.length === 0" class="empty-hint">
            本期无收入记录
          </div>
        </div>

        <!-- 支出类 -->
        <div class="category-section">
          <div class="category-header">
            <div class="category-title">
              <span class="category-icon expense">💸</span>
              <span>支出</span>
            </div>
            <div class="category-total expense">-{{ formatCurrency(data.expenses.total_cny) }}</div>
          </div>
          <div class="items-list">
            <IncomeExpenseTreeItem v-for="item in sortedExpenseItems" :key="item.account" :item="item" type="expense"
              :default-expanded="false" :expanded-accounts="expandedAccounts" @click-account="handleAccountClick"
              @toggle-expand="handleToggleExpand" />
          </div>
          <div v-if="data.expenses.items.length === 0" class="empty-hint">
            本期无支出记录
          </div>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { f7Page, f7Navbar, f7Link, f7Icon } from 'framework7-vue'
import { f7 } from 'framework7-vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { reportsApi, type IncomeStatementResponse, type IncomeExpenseItem } from '../../api/reports'
import IncomeExpenseTreeItem from '../../components/IncomeExpenseTreeItem.vue'

const router = useRouter()

// 状态缓存 key
const STATE_CACHE_KEY = 'income-statement-state'

interface CachedState {
  scrollPosition: number
  startDate: string
  endDate: string
  expandedAccounts: string[] // 展开的账户列表
}

function goBack() {
  // 返回时清除缓存
  sessionStorage.removeItem(STATE_CACHE_KEY)
  router.back()
}

function openAIContext() {
  router.push({
    path: '/ai',
    query: {
      prompt: '解释一下当前利润表，重点说明收入、支出和净利润变化',
      source_page: '/reports/income-statement',
      start_date: startDate.value,
      end_date: endDate.value,
    }
  })
}

// 保存页面状态
function savePageState() {
  const pageContent = document.querySelector('.page[data-name="income-statement"] .page-content')
  const state: CachedState = {
    scrollPosition: pageContent ? pageContent.scrollTop : 0,
    startDate: startDate.value,
    endDate: endDate.value,
    expandedAccounts: Array.from(expandedAccounts.value)
  }
  sessionStorage.setItem(STATE_CACHE_KEY, JSON.stringify(state))
}

// 恢复滚动位置
function restoreScrollPosition(position: number) {
  // 使用 requestAnimationFrame 确保 DOM 已完全渲染
  requestAnimationFrame(() => {
    setTimeout(() => {
      const pageContent = document.querySelector('.page[data-name="income-statement"] .page-content')
      if (pageContent) {
        pageContent.scrollTop = position
      }
    }, 50)
  })
}

// 获取缓存的状态
function getCachedState(): CachedState | null {
  const cached = sessionStorage.getItem(STATE_CACHE_KEY)
  if (cached) {
    try {
      return JSON.parse(cached)
    } catch {
      return null
    }
  }
  return null
}

// 路由离开前保存状态（进入详情页时保存）
onBeforeRouteLeave((to) => {
  // 只有进入账户详情页时才保存状态
  if (to.path === '/reports/account-detail') {
    savePageState()
  }
})

const loading = ref(false)
const error = ref('')
const data = ref<IncomeStatementResponse | null>(null)

// 日期相关 - 使用本地日期格式化避免时区问题
function formatDateValue(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// 初始化状态（从缓存恢复或使用默认值）
function getInitialState(): { start: string, end: string, expandedAccounts: Set<string> } {
  const cached = getCachedState()
  if (cached) {
    return {
      start: cached.startDate,
      end: cached.endDate,
      expandedAccounts: new Set(cached.expandedAccounts || [])
    }
  }
  const today = new Date()
  return {
    start: formatDateValue(new Date(today.getFullYear(), today.getMonth(), 1)),
    end: formatDateValue(today),
    expandedAccounts: new Set()
  }
}

const initialState = getInitialState()
const startDate = ref(initialState.start)
const endDate = ref(initialState.end)

// 展开的账户集合（从缓存初始化）
const expandedAccounts = ref<Set<string>>(initialState.expandedAccounts)

// 处理账户展开/折叠事件
function handleToggleExpand(account: string, expanded: boolean) {
  if (expanded) {
    expandedAccounts.value.add(account)
  } else {
    expandedAccounts.value.delete(account)
  }
}

// 日期范围选择器实例
let dateRangeCalendar: any = null

function openDateRangePicker() {
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
    cssClass: 'report-date-calendar',
    value: [
      new Date(startDate.value || new Date()),
      new Date(endDate.value || new Date())
    ],
    on: {
      change: function (calendar: any, value: unknown) {
        const values = value as Date[]
        // 当选择了两个日期（完整的日期范围）时，自动关闭日历
        if (values && values.length === 2 && values[0] && values[1]) {
          startDate.value = formatDateValue(values[0])
          endDate.value = formatDateValue(values[1])
          calendar.close()
          loadIncomeStatement()
        }
      }
    }
  })

  dateRangeCalendar.open()
}

function formatDisplayDate(dateStr: string): string {
  if (!dateStr) return '-'
  // 解析 YYYY-MM-DD 格式，避免时区问题
  const parts = dateStr.split('-')
  if (parts.length === 3 && parts[1] && parts[2]) {
    const month = parseInt(parts[1], 10)
    const day = parseInt(parts[2], 10)
    return `${month}月${day}日`
  }
  return dateStr
}

onBeforeUnmount(() => {
  if (dateRangeCalendar) {
    dateRangeCalendar.destroy()
    dateRangeCalendar = null
  }
})

// 日期预设
interface DatePreset {
  label: string
  getRange: () => { start: string, end: string }
}

const datePresets: DatePreset[] = [
  {
    label: '本月',
    getRange: (): { start: string, end: string } => {
      const now = new Date()
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      return {
        start: formatDateValue(start),
        end: formatDateValue(now)
      }
    }
  },
  {
    label: '上月',
    getRange: (): { start: string, end: string } => {
      const now = new Date()
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const end = new Date(now.getFullYear(), now.getMonth(), 0)
      return {
        start: formatDateValue(start),
        end: formatDateValue(end)
      }
    }
  },
  {
    label: '本季度',
    getRange: (): { start: string, end: string } => {
      const now = new Date()
      const quarter = Math.floor(now.getMonth() / 3)
      const start = new Date(now.getFullYear(), quarter * 3, 1)
      return {
        start: formatDateValue(start),
        end: formatDateValue(now)
      }
    }
  },
  {
    label: '本年',
    getRange: (): { start: string, end: string } => {
      const now = new Date()
      const start = new Date(now.getFullYear(), 0, 1)
      return {
        start: formatDateValue(start),
        end: formatDateValue(now)
      }
    }
  }
]

// 图表颜色
const incomeColors = ['#34c759', '#30d158', '#32de84', '#98fb98', '#90ee90']
const expenseColors = ['#ff3b30', '#ff6b6b', '#ff9500', '#ffcc00', '#ff69b4']

// 递归排序 items（按金额倒序）
function sortItemsByAmount(items: IncomeExpenseItem[]): IncomeExpenseItem[] {
  return [...items]
    .sort((a, b) => b.total_cny - a.total_cny)
    .map(item => ({
      ...item,
      children: item.children && item.children.length > 0
        ? sortItemsByAmount(item.children)
        : []
    }))
}

// 排序后的收入项（按金额倒序）
const sortedIncomeItems = computed(() => {
  if (!data.value) return []
  return sortItemsByAmount(data.value.income.items)
})

// 排序后的支出项（按金额倒序）
const sortedExpenseItems = computed(() => {
  if (!data.value) return []
  return sortItemsByAmount(data.value.expenses.items)
})

// 获取 Top 收入项（用于图表）
const topIncomeItems = computed(() => {
  if (!data.value) return []
  return flattenItems(data.value.income.items)
    .sort((a, b) => b.total_cny - a.total_cny)
    .slice(0, 5)
})

// 获取 Top 支出项（用于图表）
const topExpenseItems = computed(() => {
  if (!data.value) return []
  return flattenItems(data.value.expenses.items)
    .sort((a, b) => b.total_cny - a.total_cny)
    .slice(0, 5)
})

function flattenItems(items: IncomeExpenseItem[]): IncomeExpenseItem[] {
  const result: IncomeExpenseItem[] = []
  function traverse(items: IncomeExpenseItem[]) {
    for (const item of items) {
      if (item.children && item.children.length > 0) {
        traverse(item.children)
      } else {
        result.push(item)
      }
    }
  }
  traverse(items)
  return result
}

function isPresetActive(preset: DatePreset): boolean {
  const range = preset.getRange()
  return startDate.value === range.start && endDate.value === range.end
}

function applyPreset(preset: DatePreset) {
  const range = preset.getRange()
  startDate.value = range.start
  endDate.value = range.end
  loadIncomeStatement()
}

function formatCurrency(amount: number): string {
  return `¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

async function loadIncomeStatement(scrollPositionToRestore?: number) {
  loading.value = true
  error.value = ''

  try {
    data.value = await reportsApi.getIncomeStatement({
      start_date: startDate.value,
      end_date: endDate.value
    })
    // 数据加载完成后恢复滚动位置
    if (scrollPositionToRestore !== undefined && scrollPositionToRestore > 0) {
      restoreScrollPosition(scrollPositionToRestore)
    }
  } catch (err: any) {
    error.value = err.message || '加载失败，请重试'
    console.error('Failed to load income statement:', err)
  } finally {
    loading.value = false
  }
}

function handleAccountClick(item: IncomeExpenseItem) {
  router.push({
    path: '/reports/account-detail',
    query: {
      account: item.account,
      start_date: startDate.value,
      end_date: endDate.value
    }
  })
}

onMounted(() => {
  // 检查是否有缓存的状态（从详情页返回）
  const cachedState = getCachedState()
  const scrollPosition = cachedState?.scrollPosition
  // 加载数据并在完成后恢复滚动位置
  loadIncomeStatement(scrollPosition)
  // 恢复状态后清除缓存
  if (cachedState) {
    sessionStorage.removeItem(STATE_CACHE_KEY)
  }
})
</script>

<style scoped>
.income-statement-content {
  min-height: 100%;
  background: var(--bg-primary);
  padding-bottom: 20px;
  transition: background-color 0.3s;
}

/* 日期范围选择器 */
.date-range-section {
  background: var(--bg-secondary);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: background-color 0.15s;
}

.date-range-section:active {
  background: var(--bg-tertiary);
}

.date-range-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--ios-blue);
}

.date-separator {
  font-size: 14px;
  color: #8e8e93;
}

.date-icon {
  color: var(--ios-blue);
}

/* 快捷日期选择 */
.quick-date-section {
  background: var(--bg-secondary);
  padding: 8px 16px 12px;
  display: flex;
  gap: 8px;
  border-top: 0.5px solid var(--separator);
  margin-bottom: 8px;
  overflow-x: auto;
}

.quick-date-btn {
  padding: 6px 14px;
  border: 1px solid var(--separator);
  border-radius: 16px;
  background: var(--bg-secondary);
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-date-btn.active {
  background: var(--ios-blue);
  border-color: var(--ios-blue);
  color: #fff;
}

/* 加载状态 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--separator);
  border-top-color: var(--ios-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  margin-top: 12px;
  font-size: 14px;
  color: #8e8e93;
}

/* 错误状态 */
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
}

.error-text {
  font-size: 15px;
  color: var(--ios-red);
  margin-bottom: 16px;
}

.retry-btn {
  padding: 10px 24px;
  background: var(--ios-blue);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}

/* 汇总卡片 */
.summary-card {
  background: var(--bg-secondary);
  margin: 0 16px 12px;
  border-radius: 12px;
  padding: 20px 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.main-row {
  text-align: center;
  margin-bottom: 16px;
}

.summary-label {
  font-size: 13px;
  color: #8e8e93;
  margin-bottom: 4px;
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
}

.summary-value.positive {
  color: var(--ios-green);
}

.summary-value.negative {
  color: var(--ios-red);
}

.summary-divider {
  height: 1px;
  background: var(--separator);
  margin-bottom: 16px;
}

.summary-details {
  display: flex;
  justify-content: space-around;
}

.summary-item {
  text-align: center;
}

.item-label {
  display: block;
  font-size: 12px;
  color: #8e8e93;
  margin-bottom: 4px;
}

.item-value {
  font-size: 16px;
  font-weight: 600;
}

.item-value.income {
  color: var(--ios-green);
}

.item-value.expense {
  color: var(--ios-red);
}

/* 图表卡片 */
.chart-card {
  background: var(--bg-secondary);
  margin: 0 16px 12px;
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  font-size: 13px;
  font-weight: 600;
  color: #8e8e93;
  text-transform: uppercase;
  padding: 12px 16px 8px;
}

.pie-chart-container {
  padding: 0 16px 16px;
}

.pie-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}

.legend-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
}

.legend-value {
  font-size: 14px;
  color: #8e8e93;
  font-weight: 500;
}

/* 分类区域 */
.category-section {
  background: var(--bg-secondary);
  margin: 0 16px 12px;
  border-radius: 12px;
  overflow: hidden;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--separator);
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.category-icon {
  font-size: 18px;
}

.category-total {
  font-size: 16px;
  font-weight: 600;
}

.category-total.income {
  color: var(--ios-green);
}

.category-total.expense {
  color: var(--ios-red);
}

.items-list {
  padding: 0;
}

.empty-hint {
  padding: 24px 16px;
  text-align: center;
  font-size: 14px;
  color: #8e8e93;
}
</style>
