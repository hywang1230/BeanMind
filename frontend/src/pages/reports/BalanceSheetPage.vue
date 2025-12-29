<template>
  <f7-page name="balance-sheet">
    <f7-navbar title="资产负债表">
      <template #left>
        <f7-link @click="goBack">
          <f7-icon f7="chevron_left"></f7-icon>
          <span></span>
        </f7-link>
      </template>
    </f7-navbar>
    
    <div class="balance-sheet-content">
      <!-- 日期选择器 -->
      <div class="date-picker-section" @click="openDatePicker">
        <div class="date-picker-label">截止日期</div>
        <div class="date-picker-value">
          <span>{{ formatDisplayDate(selectedDate || '') }}</span>
          <f7-icon f7="calendar" size="18" class="date-icon"></f7-icon>
        </div>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">加载中...</p>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="error" class="error-container">
        <p class="error-text">{{ error }}</p>
        <button @click="loadBalanceSheet()" class="retry-btn">重试</button>
      </div>
      
      <!-- 报表内容 -->
      <div v-else-if="data" class="report-body">
        <!-- 汇总卡片 -->
        <div class="summary-card">
          <div class="summary-row main-row">
            <div class="summary-label">净资产</div>
            <div class="summary-value" :class="{ negative: data.net_worth_cny < 0 }">
              {{ formatCurrency(data.net_worth_cny) }}
            </div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-details">
            <div class="summary-item">
              <span class="item-label">总资产</span>
              <span class="item-value assets">{{ formatCurrency(data.total_assets_cny) }}</span>
            </div>
            <div class="summary-item">
              <span class="item-label">总负债</span>
              <span class="item-value liabilities">{{ formatCurrency(data.total_liabilities_cny) }}</span>
            </div>
            <div class="summary-item">
              <span class="item-label">总权益</span>
              <span class="item-value equity">{{ formatCurrency(data.total_equity_cny) }}</span>
            </div>
          </div>
        </div>
        
        <!-- 汇率信息 -->
        <div v-if="data.currencies.length > 1" class="exchange-rates-card">
          <div class="card-header">汇率参考</div>
          <div class="rates-list">
            <div v-for="currency in data.currencies" :key="currency" class="rate-item">
              <span class="rate-currency">{{ currency }}</span>
              <span class="rate-value">{{ currency === 'CNY' ? '1.00' : formatRate(data.exchange_rates[currency]) }}</span>
            </div>
          </div>
        </div>
        
        <!-- 资产类 -->
        <div class="category-section">
          <div class="category-header">
            <div class="category-title">
              <span class="category-icon assets">📊</span>
              <span>资产</span>
            </div>
            <div class="category-total">{{ formatCurrency(data.assets.total_cny) }}</div>
          </div>
          <div class="accounts-list">
            <ReportAccountTreeItem 
              v-for="account in data.assets.accounts" 
              :key="account.account"
              :item="account"
              type="asset"
              :default-expanded="false"
              :expanded-accounts="expandedAccounts"
              @click-account="handleAccountClick"
              @toggle-expand="handleToggleExpand"
            />
          </div>
        </div>
        
        <!-- 负债类 -->
        <div class="category-section">
          <div class="category-header">
            <div class="category-title">
              <span class="category-icon liabilities">💳</span>
              <span>负债</span>
            </div>
            <div class="category-total liabilities">{{ formatCurrency(data.liabilities.total_cny) }}</div>
          </div>
          <div class="accounts-list">
            <ReportAccountTreeItem 
              v-for="account in data.liabilities.accounts" 
              :key="account.account"
              :item="account"
              type="liability"
              :default-expanded="false"
              :expanded-accounts="expandedAccounts"
              @click-account="handleAccountClick"
              @toggle-expand="handleToggleExpand"
            />
          </div>
        </div>
        
        <!-- 权益类 -->
        <div class="category-section">
          <div class="category-header">
            <div class="category-title">
              <span class="category-icon equity">🏦</span>
              <span>权益</span>
            </div>
            <div class="category-total equity">{{ formatCurrency(data.equity.total_cny) }}</div>
          </div>
          <div class="accounts-list">
            <ReportAccountTreeItem 
              v-for="account in data.equity.accounts" 
              :key="account.account"
              :item="account"
              type="equity"
              :default-expanded="false"
              :expanded-accounts="expandedAccounts"
              @click-account="handleAccountClick"
              @toggle-expand="handleToggleExpand"
            />
          </div>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { f7Page, f7Navbar, f7Link, f7Icon } from 'framework7-vue'
import { f7 } from 'framework7-vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { reportsApi, type BalanceSheetResponse, type AccountBalanceItem } from '../../api/reports'
import ReportAccountTreeItem from '../../components/ReportAccountTreeItem.vue'

const router = useRouter()

// 状态缓存 key
const STATE_CACHE_KEY = 'balance-sheet-state'

interface CachedState {
  scrollPosition: number
  selectedDate: string
  expandedAccounts: string[] // 展开的账户列表
}

function goBack() {
  // 返回时清除缓存
  sessionStorage.removeItem(STATE_CACHE_KEY)
  router.back()
}

// 保存页面状态
function savePageState() {
  const pageContent = document.querySelector('.page[data-name="balance-sheet"] .page-content')
  const state: CachedState = {
    scrollPosition: pageContent ? pageContent.scrollTop : 0,
    selectedDate: selectedDate.value,
    expandedAccounts: Array.from(expandedAccounts.value)
  }
  sessionStorage.setItem(STATE_CACHE_KEY, JSON.stringify(state))
}

// 恢复滚动位置
function restoreScrollPosition(position: number) {
  // 使用 requestAnimationFrame 确保 DOM 已完全渲染
  requestAnimationFrame(() => {
    setTimeout(() => {
      const pageContent = document.querySelector('.page[data-name="balance-sheet"] .page-content')
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
const data = ref<BalanceSheetResponse | null>(null)

// 初始化状态（从缓存恢复或使用默认值）
function getInitialState(): { selectedDate: string, expandedAccounts: Set<string> } {
  const cached = getCachedState()
  if (cached) {
    return {
      selectedDate: cached.selectedDate,
      expandedAccounts: new Set(cached.expandedAccounts || [])
    }
  }
  return {
    selectedDate: new Date().toISOString().split('T')[0] ?? '',
    expandedAccounts: new Set()
  }
}

const initialState = getInitialState()
const selectedDate = ref(initialState.selectedDate)

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

// 日期选择器实例
let dateCalendar: any = null

function openDatePicker() {
  if (dateCalendar) {
    dateCalendar.destroy()
    dateCalendar = null
  }
  
  dateCalendar = f7.calendar.create({
    openIn: 'customModal',
    header: true,
    headerPlaceholder: '选择截止日期',
    toolbar: true,
    toolbarCloseText: '确定',
    monthPicker: true,
    yearPicker: true,
    closeByOutsideClick: true,
    cssClass: 'report-date-calendar',
    value: [new Date(selectedDate.value || new Date())],
    on: {
      change: function (_calendar: any, value: unknown) {
        const values = value as Date[]
        if (values && values.length > 0 && values[0]) {
          selectedDate.value = formatDateValue(values[0])
        }
      },
      closed: function () {
        loadBalanceSheet()
      }
    }
  })
  
  dateCalendar.open()
}

function formatDateValue(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDisplayDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

onBeforeUnmount(() => {
  if (dateCalendar) {
    dateCalendar.destroy()
    dateCalendar = null
  }
})

function formatCurrency(amount: number): string {
  const prefix = amount < 0 ? '-' : ''
  return `${prefix}¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatRate(rate: number | undefined): string {
  if (rate === undefined) return '-'
  return rate.toFixed(4)
}

async function loadBalanceSheet(scrollPositionToRestore?: number) {
  loading.value = true
  error.value = ''
  
  try {
    data.value = await reportsApi.getBalanceSheet({
      as_of_date: selectedDate.value
    })
    // 数据加载完成后恢复滚动位置
    if (scrollPositionToRestore !== undefined && scrollPositionToRestore > 0) {
      restoreScrollPosition(scrollPositionToRestore)
    }
  } catch (err: any) {
    error.value = err.message || '加载失败，请重试'
    console.error('Failed to load balance sheet:', err)
  } finally {
    loading.value = false
  }
}

function handleAccountClick(account: AccountBalanceItem) {
  // 导航到账户明细页面
  router.push({
    path: '/reports/account-detail',
    query: {
      account: account.account,
      end_date: selectedDate.value
    }
  })
}

onMounted(() => {
  // 检查是否有缓存的状态（从详情页返回）
  const cachedState = getCachedState()
  const scrollPosition = cachedState?.scrollPosition
  // 加载数据并在完成后恢复滚动位置
  loadBalanceSheet(scrollPosition)
  // 恢复状态后清除缓存
  if (cachedState) {
    sessionStorage.removeItem(STATE_CACHE_KEY)
  }
})
</script>

<style scoped>
.balance-sheet-content {
  min-height: 100%;
  background: #f2f2f7;
  padding-bottom: 20px;
}

/* 日期选择器 */
.date-picker-section {
  background: #fff;
  padding: 12px 16px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: background-color 0.15s;
}

.date-picker-section:active {
  background-color: #f8f8f8;
}

.date-picker-label {
  font-size: 15px;
  color: #000;
  font-weight: 500;
}

.date-picker-value {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  color: #007aff;
}

.date-icon {
  color: #007aff;
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
  border: 3px solid #e5e5ea;
  border-top-color: #007aff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  color: #ff3b30;
  margin-bottom: 16px;
}

.retry-btn {
  padding: 10px 24px;
  background: #007aff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}

/* 汇总卡片 */
.summary-card {
  background: #fff;
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
  color: #34c759;
}

.summary-value.negative {
  color: #ff3b30;
}

.summary-divider {
  height: 1px;
  background: #e5e5ea;
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
  font-size: 15px;
  font-weight: 600;
  color: #000;
}

.item-value.assets { color: #34c759; }
.item-value.liabilities { color: #ff9500; }
.item-value.equity { color: #007aff; }

/* 汇率信息卡片 */
.exchange-rates-card {
  background: #fff;
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

.rates-list {
  display: flex;
  flex-wrap: wrap;
  padding: 0 16px 12px;
  gap: 12px;
}

.rate-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f8f8f8;
  border-radius: 6px;
}

.rate-currency {
  font-size: 13px;
  font-weight: 600;
  color: #000;
}

.rate-value {
  font-size: 13px;
  color: #8e8e93;
}

/* 分类区域 */
.category-section {
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 12px;
  overflow: hidden;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #f8f8f8;
  border-bottom: 1px solid #e5e5ea;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.category-icon {
  font-size: 18px;
}

.category-total {
  font-size: 16px;
  font-weight: 600;
  color: #34c759;
}

.category-total.liabilities {
  color: #ff9500;
}

.category-total.equity {
  color: #007aff;
}

.accounts-list {
  padding: 0;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .balance-sheet-content {
    background: #000;
  }
  
  .date-picker-section,
  .summary-card,
  .exchange-rates-card,
  .category-section {
    background: #1c1c1e;
  }
  
  .date-picker-section:active {
    background-color: #2c2c2e;
  }
  
  .date-picker-label {
    color: #fff;
  }
  
  .date-picker-value {
    color: #0a84ff;
  }
  
  .date-icon {
    color: #0a84ff;
  }
  
  .summary-value {
    color: #30d158;
  }
  
  .summary-value.negative {
    color: #ff453a;
  }
  
  .summary-divider {
    background: #38383a;
  }
  
  .item-value {
    color: #fff;
  }
  
  .item-value.assets { color: #30d158; }
  .item-value.liabilities { color: #ff9f0a; }
  .item-value.equity { color: #0a84ff; }
  
  .rate-item {
    background: #2c2c2e;
  }
  
  .rate-currency {
    color: #fff;
  }
  
  .category-header {
    background: #2c2c2e;
    border-bottom-color: #38383a;
  }
  
  .category-title {
    color: #fff;
  }
  
  .category-total {
    color: #30d158;
  }
  
  .category-total.liabilities {
    color: #ff9f0a;
  }
  
  .category-total.equity {
    color: #0a84ff;
  }
}
</style>

