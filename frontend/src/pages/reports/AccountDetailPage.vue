<template>
  <f7-page name="account-detail">
    <f7-navbar :title="displayTitle">
      <template #left>
        <f7-link @click="goBack">
          <f7-icon f7="chevron_left"></f7-icon>
          <span></span>
        </f7-link>
      </template>
    </f7-navbar>
    
    <div class="account-detail-content">
      <!-- 日期范围选择器 -->
      <div class="date-range-section" @click="openDateRangePicker">
        <div class="date-range-display">
          <span class="date-text">{{ formatDisplayDate(startDate) }}</span>
          <span class="date-separator">至</span>
          <span class="date-text">{{ formatDisplayDate(endDate) }}</span>
        </div>
        <f7-icon f7="calendar" size="18" class="date-icon"></f7-icon>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">加载中...</p>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="error" class="error-container">
        <p class="error-text">{{ error }}</p>
        <button @click="loadAccountDetail" class="retry-btn">重试</button>
      </div>
      
      <!-- 报表内容 -->
      <div v-else-if="data" class="report-body">
        <!-- 账户信息卡片 -->
        <div class="account-info-card">
          <div class="account-header">
            <span class="account-type-badge" :class="accountTypeClass">
              {{ accountTypeLabel }}
            </span>
            <span class="account-full-name">{{ data.account }}</span>
          </div>
        </div>
        
        <!-- 余额汇总卡片 -->
        <div class="balance-summary-card">
          <div class="balance-row">
            <div class="balance-item">
              <span class="balance-label">期初余额</span>
              <span class="balance-value">{{ formatCurrency(data.opening_balance_cny) }}</span>
              <div v-if="hasMultipleCurrencies(data.opening_balances)" class="balance-detail">
                <span v-for="(amount, currency) in data.opening_balances" :key="currency" class="currency-amount">
                  {{ currency }} {{ formatAmount(amount) }}
                </span>
              </div>
            </div>
            <div class="balance-arrow">→</div>
            <div class="balance-item">
              <span class="balance-label">期末余额</span>
              <span class="balance-value current">{{ formatCurrency(data.current_balance_cny) }}</span>
              <div v-if="hasMultipleCurrencies(data.current_balances)" class="balance-detail">
                <span v-for="(amount, currency) in data.current_balances" :key="currency" class="currency-amount">
                  {{ currency }} {{ formatAmount(amount) }}
                </span>
              </div>
            </div>
          </div>
          
          <div class="change-row">
            <span class="change-label">本期变动</span>
            <span class="change-value" :class="{ positive: data.period_change_cny >= 0, negative: data.period_change_cny < 0 }">
              {{ data.period_change_cny >= 0 ? '+' : '' }}{{ formatCurrency(data.period_change_cny) }}
            </span>
          </div>
        </div>
        
        <!-- 交易列表 -->
        <div class="transactions-section">
          <div class="section-header">
            <span class="section-title">交易明细</span>
            <span class="section-count">共 {{ data.transactions.length }} 笔</span>
          </div>
          
          <div v-if="data.transactions.length === 0" class="empty-state">
            <p class="empty-text">本期无交易记录</p>
          </div>
          
          <div v-else class="transactions-list">
            <div 
              v-for="(txn, index) in data.transactions" 
              :key="index"
              class="transaction-item"
              @click="viewTransactionDetail(txn)"
            >
              <div class="txn-main">
                <div class="txn-info">
                  <div class="txn-counterpart-main">{{ txn.counterpart_accounts.length > 0 ? formatCounterparts(txn.counterpart_accounts) : '(无对方账户)' }}</div>
                  <div class="txn-meta">
                    <span class="txn-date">{{ formatDate(txn.date) }}</span>
                    <span v-if="txn.payee" class="txn-payee">{{ txn.payee }}</span>
                  </div>
                </div>
                <div class="txn-amount" :class="{ positive: txn.amount >= 0, negative: txn.amount < 0 }">
                  {{ txn.amount >= 0 ? '+' : '' }}{{ formatCurrencyWithUnit(txn.amount, txn.currency) }}
                </div>
              </div>
              
              <div class="txn-extra">
                <div class="txn-balance">
                  余额: {{ formatCurrencyWithUnit(txn.balance, txn.currency) }}
                </div>
                <div v-if="txn.description" class="txn-desc-secondary">
                  {{ txn.description }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { f7Page, f7Navbar, f7Link, f7Icon } from 'framework7-vue'
import { f7 } from 'framework7-vue'
import { useRoute, useRouter } from 'vue-router'
import { reportsApi, type AccountDetailResponse } from '../../api/reports'

const route = useRoute()
const router = useRouter()

function goBack() {
  router.back()
}

const loading = ref(false)
const error = ref('')
const data = ref<AccountDetailResponse | null>(null)

// 从路由获取账户名和日期
const accountName = ref('')
const startDate = ref('')
const endDate = ref('')

// 日期范围选择器实例
let dateRangeCalendar: any = null

function formatDateValue(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

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
      startDate.value ? new Date(startDate.value) : new Date(),
      endDate.value ? new Date(endDate.value) : new Date()
    ],
    on: {
      change: function (calendar: any, value: unknown) {
        const values = value as Date[]
        // 当选择了两个日期（完整的日期范围）时，自动关闭日历
        if (values && values.length === 2 && values[0] && values[1]) {
          startDate.value = formatDateValue(values[0])
          endDate.value = formatDateValue(values[1])
          calendar.close()
          loadAccountDetail()
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

// 显示标题
const displayTitle = computed(() => {
  if (data.value) {
    return data.value.display_name
  }
  return '账户明细'
})

// 账户类型相关
const accountTypeClass = computed(() => {
  if (!data.value) return ''
  const type = data.value.account_type
  if (type === 'Assets') return 'assets'
  if (type === 'Liabilities') return 'liabilities'
  if (type === 'Equity') return 'equity'
  if (type === 'Income') return 'income'
  if (type === 'Expenses') return 'expenses'
  return ''
})

const accountTypeLabel = computed(() => {
  if (!data.value) return ''
  const typeMap: Record<string, string> = {
    'Assets': '资产',
    'Liabilities': '负债',
    'Equity': '权益',
    'Income': '收入',
    'Expenses': '支出'
  }
  return typeMap[data.value.account_type] || data.value.account_type
})

function hasMultipleCurrencies(balances: Record<string, number>): boolean {
  return Object.keys(balances).length > 1 || !('CNY' in balances)
}

function formatCurrency(amount: number): string {
  const prefix = amount < 0 ? '-' : ''
  return `${prefix}¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatCurrencyWithUnit(amount: number, currency: string): string {
  const formattedAmount = Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (currency === 'CNY') {
    return `${amount < 0 ? '-' : ''}¥${formattedAmount}`
  }
  return `${amount < 0 ? '-' : ''}${currency} ${formattedAmount}`
}

function formatAmount(amount: number): string {
  return amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

function formatCounterparts(accounts: string[]): string {
  // 简化账户名显示
  return accounts.map(acc => {
    const parts = acc.split(':')
    return parts.length > 1 ? parts.slice(1).join(':') : acc
  }).join(', ')
}

async function loadAccountDetail() {
  if (!accountName.value) return
  
  loading.value = true
  error.value = ''
  
  try {
    data.value = await reportsApi.getAccountDetail({
      account: accountName.value,
      start_date: startDate.value || undefined,
      end_date: endDate.value || undefined
    })
  } catch (err: any) {
    error.value = err.message || '加载失败，请重试'
    console.error('Failed to load account detail:', err)
  } finally {
    loading.value = false
  }
}

function viewTransactionDetail(txn: any) {
  // TODO: 可以跳转到交易详情页
  console.log('View transaction:', txn)
}

// 初始化
onMounted(() => {
  // 从路由参数获取账户名和日期
  accountName.value = (route.query.account as string) || ''
  startDate.value = (route.query.start_date as string) || ''
  endDate.value = (route.query.end_date as string) || ''
  
  // 如果没有日期，设置默认为本月
  if (!startDate.value) {
    const today = new Date()
    startDate.value = formatDateValue(new Date(today.getFullYear(), today.getMonth(), 1))
  }
  if (!endDate.value) {
    endDate.value = formatDateValue(new Date())
  }
  
  if (accountName.value) {
    loadAccountDetail()
  } else {
    error.value = '未指定账户'
  }
})

// 监听路由变化
watch(() => route.query, (newQuery) => {
  if (newQuery.account && newQuery.account !== accountName.value) {
    accountName.value = newQuery.account as string
    startDate.value = newQuery.start_date as string || startDate.value
    endDate.value = newQuery.end_date as string || endDate.value
    loadAccountDetail()
  }
})
</script>

<style scoped>
.account-detail-content {
  min-height: 100%;
  background: #f2f2f7;
  padding-bottom: 20px;
}

/* 日期范围选择器 */
.date-range-section {
  background: #fff;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.date-range-section:active {
  background: #f8f8f8;
}

.date-range-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-text {
  font-size: 16px;
  font-weight: 500;
  color: #007aff;
}

.date-separator {
  font-size: 14px;
  color: #8e8e93;
}

.date-icon {
  color: #007aff;
}

/* 加载和错误状态 */
.loading-container,
.error-container {
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

/* 账户信息卡片 */
.account-info-card {
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 12px;
  padding: 16px;
}

.account-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.account-type-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.account-type-badge.assets { background: #dcf8e8; color: #34c759; }
.account-type-badge.liabilities { background: #fff2e0; color: #ff9500; }
.account-type-badge.equity { background: #e8f0ff; color: #007aff; }
.account-type-badge.income { background: #dcf8e8; color: #34c759; }
.account-type-badge.expenses { background: #ffe5e5; color: #ff3b30; }

.account-full-name {
  font-size: 14px;
  color: #8e8e93;
  word-break: break-all;
}

/* 余额汇总卡片 */
.balance-summary-card {
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 12px;
  padding: 16px;
}

.balance-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.balance-item {
  text-align: center;
  flex: 1;
}

.balance-label {
  display: block;
  font-size: 12px;
  color: #8e8e93;
  margin-bottom: 4px;
}

.balance-value {
  font-size: 18px;
  font-weight: 600;
  color: #000;
}

.balance-value.current {
  color: #007aff;
}

.balance-detail {
  margin-top: 4px;
}

.currency-amount {
  display: block;
  font-size: 11px;
  color: #8e8e93;
}

.balance-arrow {
  font-size: 18px;
  color: #c6c6c8;
  margin: 0 8px;
}

.change-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #e5e5ea;
}

.change-label {
  font-size: 14px;
  color: #8e8e93;
}

.change-value {
  font-size: 16px;
  font-weight: 600;
}

.change-value.positive { color: #34c759; }
.change-value.negative { color: #ff3b30; }

/* 交易列表 */
.transactions-section {
  background: #fff;
  margin: 0 16px;
  border-radius: 12px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #f8f8f8;
  border-bottom: 1px solid #e5e5ea;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #000;
}

.section-count {
  font-size: 13px;
  color: #8e8e93;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
}

.empty-text {
  font-size: 14px;
  color: #8e8e93;
}

.transactions-list {
  padding: 0;
}

.transaction-item {
  padding: 12px 16px;
  border-bottom: 0.5px solid #e5e5ea;
  cursor: pointer;
  transition: background-color 0.15s;
}

.transaction-item:last-child {
  border-bottom: none;
}

.transaction-item:active {
  background: #f8f8f8;
}

.txn-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}

.txn-info {
  flex: 1;
  min-width: 0;
}

.txn-counterpart-main {
  font-size: 15px;
  color: #000;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.txn-desc-secondary {
  font-size: 12px;
  color: #8e8e93;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
  text-align: right;
}

.txn-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #8e8e93;
}

.txn-amount {
  font-size: 15px;
  font-weight: 600;
  margin-left: 12px;
  flex-shrink: 0;
}

.txn-amount.positive { color: #34c759; }
.txn-amount.negative { color: #ff3b30; }

.txn-extra {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #8e8e93;
}


/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .account-detail-content {
    background: #000;
  }
  
  .date-range-section,
  .account-info-card,
  .balance-summary-card,
  .transactions-section {
    background: #1c1c1e;
  }
  
  .date-input {
    background: #2c2c2e;
    border-color: #38383a;
    color: #0a84ff;
  }
  
  .account-type-badge.assets { background: rgba(48, 209, 88, 0.2); color: #30d158; }
  .account-type-badge.liabilities { background: rgba(255, 159, 10, 0.2); color: #ff9f0a; }
  .account-type-badge.equity { background: rgba(10, 132, 255, 0.2); color: #0a84ff; }
  .account-type-badge.income { background: rgba(48, 209, 88, 0.2); color: #30d158; }
  .account-type-badge.expenses { background: rgba(255, 69, 58, 0.2); color: #ff453a; }
  
  .balance-value {
    color: #fff;
  }
  
  .balance-value.current {
    color: #0a84ff;
  }
  
  .change-row {
    border-top-color: #38383a;
  }
  
  .change-value.positive { color: #30d158; }
  .change-value.negative { color: #ff453a; }
  
  .section-header {
    background: #2c2c2e;
    border-bottom-color: #38383a;
  }
  
  .section-title {
    color: #fff;
  }
  
  .transaction-item {
    border-bottom-color: #38383a;
  }
  
  .transaction-item:active {
    background: #2c2c2e;
  }
  
  .txn-counterpart-main {
    color: #fff;
  }
  
  .txn-amount.positive { color: #30d158; }
  .txn-amount.negative { color: #ff453a; }
}
</style>

