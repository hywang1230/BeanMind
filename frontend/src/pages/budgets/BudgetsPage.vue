<template>
  <f7-page name="budgets">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>预算管理</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="navigateToCreate">
          <f7-icon ios="f7:plus" md="material:add" />
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <!-- 加载状态 -->
    <div v-if="loading && budgets.length === 0" class="loading-container">
      <f7-preloader></f7-preloader>
    </div>

    <!-- 空状态 -->
    <div v-else-if="budgets.length === 0" class="empty-state">
      <div class="empty-icon">🎯</div>
      <div class="empty-text">暂无预算</div>
      <f7-button fill round @click="navigateToCreate">
        创建预算
      </f7-button>
    </div>

    <!-- 预算概览卡片 -->
    <f7-block v-if="budgets.length > 0" class="summary-block">
      <div class="summary-card">
        <div class="summary-header">
          <span class="summary-title">本月预算概览</span>
          <f7-chip :color="getOverallStatusColor()" outline>
            {{ getOverallStatusText() }}
          </f7-chip>
        </div>
        <div class="summary-stats">
          <div class="stat-item">
            <span class="stat-value">¥{{ formatNumber(totalBudget) }}</span>
            <span class="stat-label">预算总额</span>
          </div>
          <div class="stat-item">
            <span class="stat-value spent">¥{{ formatNumber(totalSpent) }}</span>
            <span class="stat-label">已支出</span>
          </div>
          <div class="stat-item">
            <span class="stat-value" :class="totalRemaining >= 0 ? 'remaining' : 'exceeded'">
              ¥{{ formatNumber(Math.abs(totalRemaining)) }}
            </span>
            <span class="stat-label">{{ totalRemaining >= 0 ? '剩余' : '超支' }}</span>
          </div>
        </div>
        <div class="summary-progress">
          <f7-progressbar :progress="Math.min(overallRate, 100)" :class="getProgressClass(overallRate)" />
          <span class="progress-text">{{ overallRate.toFixed(1) }}%</span>
        </div>
      </div>
    </f7-block>

    <!-- 预算列表 -->
    <f7-list v-if="budgets.length > 0" strong-ios dividers-ios inset class="budgets-list">
      <f7-list-item v-for="budget in budgets" :key="budget.id" :title="budget.name" :subtitle="getPeriodText(budget)"
        link="#" @click="viewBudgetDetail(budget)" class="budget-item">
        <template #media>
          <div class="budget-icon" :class="getStatusClass(budget.status)">
            <f7-icon ios="f7:chart_pie_fill" size="18" />
          </div>
        </template>
        <template #after>
          <div class="budget-after">
            <span class="usage-rate" :class="getStatusClass(budget.status)">
              {{ budget.overall_usage_rate.toFixed(0) }}%
            </span>
            <f7-icon ios="f7:chevron_right" size="14" class="chevron" />
          </div>
        </template>
        <template #inner>
          <div class="budget-inner-content">
            <div class="budget-amounts">
              <span class="budget-spent">¥{{ formatNumber(budget.total_spent) }}</span>
              <span class="budget-separator">/</span>
              <span class="budget-total">¥{{ formatNumber(budget.total_budget) }}</span>
            </div>
            <f7-progressbar :progress="Math.min(budget.overall_usage_rate, 100)"
              :class="getProgressClass(budget.overall_usage_rate)" class="budget-progress" />
          </div>
        </template>
      </f7-list-item>
    </f7-list>

    <!-- 刷新提示 -->
    <f7-block v-if="budgets.length > 0" class="refresh-hint">
      <f7-link @click="loadBudgets" class="refresh-link">
        <f7-icon ios="f7:arrow_clockwise" size="16" />
        <span>刷新数据</span>
      </f7-link>
    </f7-block>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { budgetsApi, type Budget } from '../../api/budgets'
import { f7 } from 'framework7-vue'

const router = useRouter()

const loading = ref(false)
const budgets = ref<Budget[]>([])

// 计算属性
const totalBudget = computed(() => budgets.value.reduce((sum, b) => sum + b.total_budget, 0))
const totalSpent = computed(() => budgets.value.reduce((sum, b) => sum + b.total_spent, 0))
const totalRemaining = computed(() => totalBudget.value - totalSpent.value)
const overallRate = computed(() => {
  if (totalBudget.value === 0) return 0
  return (totalSpent.value / totalBudget.value) * 100
})

function formatNumber(num: number): string {
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getPeriodText(budget: Budget): string {
  // 如果是循环预算，优先显示循环类型
  if (budget.cycle_type && budget.cycle_type !== 'NONE') {
    const cycleTypes: Record<string, string> = {
      MONTHLY: '按月循环',
      YEARLY: '按年循环'
    }
    const cycleTypeText = cycleTypes[budget.cycle_type] || budget.cycle_type
    return `${cycleTypeText} · ${budget.items.length} 个类别`
  }

  // 非循环预算，显示周期类型
  const types: Record<string, string> = {
    MONTHLY: '月度预算',
    YEARLY: '年度预算',
    CUSTOM: '自定义周期'
  }
  const typeText = types[budget.period_type] || budget.period_type
  return `${typeText} · ${budget.items.length} 个类别`
}

function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    normal: 'status-normal',
    warning: 'status-warning',
    exceeded: 'status-exceeded'
  }
  return classes[status] || ''
}

function getProgressClass(rate: number): string {
  if (rate >= 100) return 'progress-exceeded'
  if (rate >= 80) return 'progress-warning'
  return 'progress-normal'
}

function getOverallStatusColor(): string {
  if (overallRate.value >= 100) return 'red'
  if (overallRate.value >= 80) return 'orange'
  return 'green'
}

function getOverallStatusText(): string {
  if (overallRate.value >= 100) return '超支'
  if (overallRate.value >= 80) return '警告'
  return '正常'
}

async function loadBudgets() {
  loading.value = true
  try {
    const response = await budgetsApi.getActiveBudgets()
    budgets.value = response.budgets
  } catch (error) {
    console.error('Failed to load budgets:', error)
    f7.toast.create({
      text: '加载预算失败',
      position: 'center',
      closeTimeout: 2000
    }).open()
  } finally {
    loading.value = false
  }
}

function viewBudgetDetail(budget: Budget) {
  router.push(`/budgets/${budget.id}`)
}

function navigateToCreate() {
  router.push('/budgets/create')
}

function goBack() {
  router.back()
}

onMounted(() => {
  loadBudgets()
})
</script>

<style scoped>
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
  color: var(--text-primary);
  opacity: 0.6;
  margin-bottom: 24px;
}

/* 概览卡片 */
.summary-block {
  margin-top: 0;
  padding-top: 16px;
}

.summary-card {
  background: var(--bg-secondary);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.summary-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.spent {
  color: var(--ios-orange);
}

.stat-value.remaining {
  color: var(--ios-green);
}

.stat-value.exceeded {
  color: var(--ios-red);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.summary-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.summary-progress :deep(.progressbar) {
  flex: 1;
  height: 8px;
  border-radius: 4px;
}

.progress-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 50px;
  text-align: right;
}

/* 进度条颜色 */
:deep(.progress-normal .progressbar-fill) {
  background: linear-gradient(90deg, var(--ios-green), #66d97c);
}

:deep(.progress-warning .progressbar-fill) {
  background: linear-gradient(90deg, var(--ios-orange), #ffb347);
}

:deep(.progress-exceeded .progressbar-fill) {
  background: linear-gradient(90deg, var(--ios-red), #ff6b6b);
}

/* 预算列表 */
.budgets-list {
  margin-top: 8px;
}

.budget-item {
  --f7-list-item-min-height: auto;
}

.budget-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.budget-icon.status-normal {
  background: rgba(52, 199, 89, 0.12);
  color: var(--ios-green);
}

.budget-icon.status-warning {
  background: rgba(255, 149, 0, 0.12);
  color: var(--ios-orange);
}

.budget-icon.status-exceeded {
  background: rgba(255, 59, 48, 0.12);
  color: var(--ios-red);
}

.budget-after {
  display: flex;
  align-items: center;
  gap: 8px;
}

.usage-rate {
  font-size: 14px;
  font-weight: 600;
}

.usage-rate.status-normal {
  color: var(--ios-green);
}

.usage-rate.status-warning {
  color: var(--ios-orange);
}

.usage-rate.status-exceeded {
  color: var(--ios-red);
}

.chevron {
  color: var(--text-tertiary);
}

.budget-inner-content {
  padding-top: 8px;
}

.budget-amounts {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}

.budget-spent {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.budget-separator {
  font-size: 13px;
  color: var(--text-tertiary);
}

.budget-total {
  font-size: 13px;
  color: var(--text-secondary);
}

.budget-progress {
  height: 4px;
  border-radius: 2px;
}

/* 刷新提示 */
.refresh-hint {
  text-align: center;
  padding-bottom: 32px;
}

.refresh-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 暗色模式支持 */
:root {
  --text-primary: #1c1c1e;
  --text-secondary: #8e8e93;
  --text-tertiary: #c7c7cc;
  --bg-secondary: #ffffff;
  --ios-green: #34c759;
  --ios-orange: #ff9500;
  --ios-red: #ff3b30;
}

@media (prefers-color-scheme: dark) {
  :root {
    --text-primary: #ffffff;
    --text-secondary: #98989d;
    --text-tertiary: #48484a;
    --bg-secondary: #1c1c1e;
  }
}
</style>
