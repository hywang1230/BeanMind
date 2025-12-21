<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h1>仪表盘</h1>
      <button @click="handleLogout" class="logout-btn">退出</button>
    </div>
    
    <!-- 总资产概览 -->
    <div class="asset-overview">
      <div class="overview-card">
        <div class="card-label">总资产</div>
        <div class="card-value">¥ {{ formatNumber(totalAssets) }}</div>
      </div>
    </div>
    
    <!-- 本月收支 -->
    <div class="monthly-summary">
      <div class="summary-card income">
        <div class="card-icon">📈</div>
        <div class="card-content">
          <div class="card-label">本月收入</div>
          <div class="card-value">¥ {{ formatNumber(monthlyIncome) }}</div>
        </div>
      </div>
      
      <div class="summary-card expense">
        <div class="card-icon">📉</div>
        <div class="card-content">
          <div class="card-label">本月支出</div>
          <div class="card-value">¥ {{ formatNumber(monthlyExpense) }}</div>
        </div>
      </div>
    </div>
    
    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h2 class="section-title">快捷操作</h2>
      <div class="action-grid">
        <button @click="navigateTo('/transactions/add')" class="action-btn">
          <span class="action-icon">➕</span>
          <span class="action-label">记一笔</span>
        </button>
        <button @click="navigateTo('/transactions')" class="action-btn">
          <span class="action-icon">📊</span>
          <span class="action-label">交易记录</span>
        </button>
        <button @click="navigateTo('/accounts')" class="action-btn">
          <span class="action-icon">💰</span>
          <span class="action-label">账户管理</span>
        </button>
        <button @click="navigateTo('/budgets')" class="action-btn">
          <span class="action-icon">🎯</span>
          <span class="action-label">预算管理</span>
        </button>
      </div>
    </div>
    
    <!-- 最近交易 -->
    <div class="recent-transactions">
      <div class="section-header">
        <h2 class="section-title">最近交易</h2>
        <router-link to="/transactions" class="view-all">查看全部</router-link>
      </div>
      
      <div v-if="loading" class="loading">加载中...</div>
      
      <div v-else-if="recentTransactions.length === 0" class="empty-state">
        暂无交易记录
      </div>
      
      <div v-else class="transaction-list">
        <div
          v-for="transaction in recentTransactions"
          :key="transaction.id"
          class="transaction-item"
        >
          <div class="transaction-info">
            <div class="transaction-desc">{{ transaction.description }}</div>
            <div class="transaction-date">{{ formatDate(transaction.date) }}</div>
          </div>
          <div class="transaction-amount" :class="getAmountClass(transaction)">
            {{ formatTransactionAmount(transaction) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { transactionsApi, type Transaction } from '../../api/transactions'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const totalAssets = ref(0)
const monthlyIncome = ref(0)
const monthlyExpense = ref(0)
const recentTransactions = ref<Transaction[]>([])

function formatNumber(num: number | undefined | null): string {
  // 处理 undefined、null 和 NaN 的情况
  if (num === undefined || num === null || isNaN(num)) {
    return '0.00'
  }
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  
  return `${date.getMonth() + 1}-${date.getDate()}`
}

function getAmountClass(transaction: Transaction): string {
  const firstPosting = transaction.postings?.[0]
  if (!firstPosting) return ''
  if (firstPosting.account.startsWith('Income')) return 'positive'
  if (firstPosting.account.startsWith('Expenses')) return 'negative'
  return ''
}

function formatTransactionAmount(transaction: Transaction): string {
  const firstPosting = transaction.postings?.[0]
  if (!firstPosting || firstPosting.amount === undefined) {
    return '¥0.00'
  }
  const sign = firstPosting.amount > 0 ? '+' : ''
  return `${sign}¥${formatNumber(Math.abs(firstPosting.amount))}`
}

function navigateTo(path: string) {
  router.push(path)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

async function loadDashboardData() {
  loading.value = true
  try {
    // 获取本月起始和结束日期
    const now = new Date()
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    
    const startDateStr = startOfMonth.toISOString().split('T')[0]
    const endDateStr = endOfMonth.toISOString().split('T')[0]
    
    // 获取本月统计数据
    const stats = await transactionsApi.getStatistics(startDateStr, endDateStr)
    monthlyIncome.value = stats.total_income
    monthlyExpense.value = Math.abs(stats.total_expense)
    
    // 获取最近交易
    const response = await transactionsApi.getTransactions({
      page: 1,
      per_page: 5
    })
    recentTransactions.value = response.transactions
    
    // 计算总资产（简化版，实际应该从后端获取）
    totalAssets.value = monthlyIncome.value - monthlyExpense.value
    
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.dashboard-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.logout-btn {
  padding: 8px 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: #f5f5f5;
}

.asset-overview {
  margin-bottom: 20px;
}

.overview-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
  border-radius: 16px;
  color: white;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.overview-card .card-label {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.overview-card .card-value {
  font-size: 36px;
  font-weight: 700;
}

.monthly-summary {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.summary-card {
  padding: 20px;
  border-radius: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.summary-card.income {
  background: #e8f5e9;
}

.summary-card.expense {
  background: #ffebee;
}

.summary-card .card-icon {
  font-size: 32px;
}

.summary-card .card-content {
  flex: 1;
}

.summary-card .card-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 4px;
}

.summary-card .card-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
}

.quick-actions {
  margin-bottom: 32px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
  transform: translateY(-2px);
}

.action-icon {
  font-size: 32px;
}

.action-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.recent-transactions {
  background: white;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e0e0e0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.view-all {
  font-size: 14px;
  color: #667eea;
  text-decoration: none;
}

.view-all:hover {
  text-decoration: underline;
}

.loading,
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.transaction-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transaction-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.transaction-item:last-child {
  border-bottom: none;
}

.transaction-info {
  flex: 1;
}

.transaction-desc {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.transaction-date {
  font-size: 12px;
  color: #999;
}

.transaction-amount {
  font-size: 18px;
  font-weight: 600;
}

.transaction-amount.positive {
  color: #4caf50;
}

.transaction-amount.negative {
  color: #f44336;
}
</style>
