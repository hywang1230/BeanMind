<template>
  <f7-page name="monthly-report">
    <f7-navbar title="AI 月报">
      <template #left>
        <f7-link @click="goBack">
          <f7-icon f7="chevron_left"></f7-icon>
          <span></span>
        </f7-link>
      </template>
    </f7-navbar>

    <div class="monthly-report-content">
      <div class="date-picker-section" @click="openMonthPicker">
        <div class="date-picker-label">目标月份</div>
        <div class="date-picker-value">
          <span>{{ formatDisplayMonth(selectedMonth) }}</span>
          <f7-icon f7="calendar" size="18" class="date-icon"></f7-icon>
        </div>
      </div>

      <MonthPickerPopup
        v-model:opened="monthPickerOpened"
        :value="selectedMonth"
        @select="onMonthSelected"
      />

      <div class="action-row">
        <button class="action-btn primary-btn" @click="generateReport(false)" :disabled="loading">
          生成月报
        </button>
        <button class="action-btn secondary-btn" @click="generateReport(true)" :disabled="loading">
          重新生成
        </button>
      </div>

      <div v-if="loading || polling" class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">{{ polling ? '后台生成中，请稍候...' : '提交中...' }}</p>
      </div>

      <div v-else-if="error" class="error-container">
        <p class="error-text">{{ error }}</p>
        <button @click="loadExistingReport" class="retry-btn">重试</button>
      </div>

      <div v-else-if="report" class="report-body">
        <div class="summary-card">
          <div class="summary-row main-row">
            <div class="summary-label">本月总结</div>
            <div class="summary-value summary-text">{{ report.summary_text }}</div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-details">
            <div class="summary-item">
              <span class="item-label">收入</span>
              <span class="item-value">{{ formatCurrency(report.report.core_metrics?.income) }}</span>
            </div>
            <div class="summary-item">
              <span class="item-label">支出</span>
              <span class="item-value">{{ formatCurrency(report.report.core_metrics?.expense) }}</span>
            </div>
            <div class="summary-item">
              <span class="item-label">结余</span>
              <span class="item-value">{{ formatCurrency(report.report.core_metrics?.balance) }}</span>
            </div>
          </div>
        </div>

        <div class="category-section">
          <div class="category-header">
            <div class="category-title">核心指标</div>
          </div>
          <div class="detail-list">
            <div class="detail-item">
              <span>储蓄率</span>
              <span>{{ formatPercent(report.report.core_metrics?.savings_rate) }}</span>
            </div>
            <div class="detail-item">
              <span>日均支出</span>
              <span>{{ formatCurrency(report.report.core_metrics?.daily_expense) }}</span>
            </div>
            <div class="detail-item">
              <span>净值变化</span>
              <span>{{ formatCurrency(report.report.core_metrics?.net_worth_change) }}</span>
            </div>
          </div>
        </div>

        <div class="category-section">
          <div class="category-header">
            <div class="category-title">支出结构</div>
          </div>
          <div class="detail-list">
            <div
              v-for="item in report.report.spending_structure?.top_categories || []"
              :key="item.category"
              class="detail-item"
            >
              <span>{{ item.category }}</span>
              <span>{{ formatCurrency(item.amount) }}</span>
            </div>
          </div>
        </div>

        <div class="category-section">
          <div class="category-header">
            <div class="category-title">异常提醒</div>
          </div>
          <div class="detail-list">
            <div
              v-for="(item, index) in localizedAnomalies"
              :key="`${item.type}-${index}`"
              class="detail-item multi-line"
            >
              <span>{{ item.label }}</span>
              <span>{{ item.message }}</span>
            </div>
          </div>
        </div>

        <div class="category-section">
          <div class="category-header">
            <div class="category-title">下月建议</div>
          </div>
          <div class="suggestion-list">
            <div
              v-for="(item, index) in suggestions"
              :key="`${index}-${item}`"
              class="suggestion-card"
            >
              <div class="suggestion-index">建议 {{ index + 1 }}</div>
              <div class="suggestion-text">{{ item }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { f7Page, f7Navbar, f7Link, f7Icon } from 'framework7-vue'
import { useRouter } from 'vue-router'
import { reportsApi, type MonthlyReportResponse } from '../../api/reports'
import MonthPickerPopup from '../../components/MonthPickerPopup.vue'

const router = useRouter()
const loading = ref(false)
const polling = ref(false)
const error = ref('')
const report = ref<MonthlyReportResponse | null>(null)
const selectedMonth = ref(new Date().toISOString().slice(0, 7))
let pollTimer: ReturnType<typeof setTimeout> | null = null
const monthPickerOpened = ref(false)
const anomalyLabelMap: Record<string, string> = {
  large_expense: '大额支出',
  category_focus: '支出集中',
  insufficient_data: '数据不足'
}
const suggestions = computed<string[]>(() => {
  const values = report.value?.report?.next_month_suggestions
  return Array.isArray(values) ? values as string[] : []
})
const localizedAnomalies = computed(() => {
  const values = report.value?.report?.anomalies
  if (!Array.isArray(values)) return []
  return values.map((item: any) => ({
    ...item,
    label: anomalyLabelMap[item?.type] || item?.type || '异常提醒'
  }))
})

function goBack() {
  router.back()
}

function openMonthPicker() {
  monthPickerOpened.value = true
}

function formatDisplayMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-')
  return `${year}年${Number(month)}月`
}

function onMonthSelected(value: string) {
  if (value === selectedMonth.value) {
    return
  }
  selectedMonth.value = value
  loadExistingReport()
}

function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '' || value === '无法判断') return '无法判断'
  const amount = Number(value)
  if (Number.isNaN(amount)) return String(value)
  return `¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '' || value === '无法判断') return '无法判断'
  const amount = Number(value)
  if (Number.isNaN(amount)) return String(value)
  return `${amount.toFixed(2)}%`
}

async function loadExistingReport() {
  loading.value = true
  error.value = ''
  try {
    report.value = await reportsApi.getMonthlyReport(selectedMonth.value)
    if (report.value?.status === 'PROCESSING') {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (err: any) {
    if (err?.response?.status === 404) {
      report.value = null
      stopPolling()
      return
    }
    error.value = err.message || '加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function generateReport(regenerate: boolean) {
  loading.value = true
  error.value = ''
  try {
    report.value = await reportsApi.generateMonthlyReport({
      report_month: selectedMonth.value,
      regenerate
    })
    if (report.value?.status === 'PROCESSING') {
      startPolling()
    }
  } catch (err: any) {
    error.value = err.message || '生成失败，请重试'
  } finally {
    loading.value = false
  }
}

function stopPolling() {
  polling.value = false
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function pollReportStatus() {
  try {
    const latest = await reportsApi.getMonthlyReport(selectedMonth.value)
    report.value = latest
    if (latest.status === 'PROCESSING') {
      pollTimer = setTimeout(pollReportStatus, 3000)
      return
    }
    if (latest.status === 'FAILED') {
      error.value = latest.summary_text || '生成失败，请重试'
    }
    stopPolling()
  } catch (err: any) {
    stopPolling()
    error.value = err.message || '加载失败，请重试'
  }
}

function startPolling() {
  stopPolling()
  polling.value = true
  pollTimer = setTimeout(pollReportStatus, 3000)
}

onMounted(() => {
  loadExistingReport()
})
</script>

<style scoped>
.monthly-report-content {
  min-height: 100%;
  background: var(--bg-primary);
  padding: 16px;
  transition: background-color 0.3s;
}

.date-picker-section,
.summary-card,
.category-section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  transition: background-color 0.3s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.date-picker-label,
.category-title,
.summary-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.date-picker-value {
  margin-top: 12px;
  padding: 12px 14px;
  border: 0.5px solid var(--separator);
  border-radius: 10px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 15px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.date-icon {
  color: #8e8e93;
  flex-shrink: 0;
}

.action-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.action-btn,
.retry-btn {
  border: none;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.action-btn {
  flex: 1;
}

.primary-btn {
  background: #ff9500;
  color: #fff;
}

.secondary-btn {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 0.5px solid var(--separator);
}

.loading-container,
.error-container {
  text-align: center;
  padding: 32px 16px;
  color: #8e8e93;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255, 149, 0, 0.2);
  border-top-color: #ff9500;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

.summary-row.main-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-text {
  line-height: 1.6;
}

.summary-divider {
  height: 0.5px;
  background: var(--separator);
  margin: 16px 0;
}

.summary-details,
.detail-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-item,
.detail-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  color: var(--text-primary);
}

.detail-item.multi-line {
  align-items: flex-start;
}

.detail-item.multi-line span:last-child {
  text-align: right;
  color: #8e8e93;
  line-height: 1.5;
}

.suggestion-card {
  border: 0.5px solid var(--separator);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--bg-primary);
}

.suggestion-index {
  font-size: 13px;
  font-weight: 600;
  color: #ff9500;
  margin-bottom: 6px;
}

.suggestion-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.item-label {
  color: #8e8e93;
}

.item-value {
  font-weight: 600;
  color: var(--text-primary);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
