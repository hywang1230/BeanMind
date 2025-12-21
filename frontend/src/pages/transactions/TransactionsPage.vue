<template>
  <div class="transactions-page">
    <div class="page-header">
      <h1>交易记录</h1>
      <button @click="navigateToAdd" class="add-btn">+ 记一笔</button>
    </div>
    
    <!-- 筛选器 -->
    <div class="filters">
      <div class="filter-tabs">
        <button
          v-for="filter in typeFilters"
          :key="filter.value"
          @click="selectTypeFilter(filter.value)"
          class="filter-tab"
          :class="{ active: currentTypeFilter === filter.value }"
        >
          {{ filter.label }}
        </button>
      </div>
      
      <div class="date-filter">
        <input
          v-model="dateRange.start"
          type="date"
          class="date-input"
          placeholder="开始日期"
        />
        <span class="date-separator">-</span>
        <input
          v-model="dateRange.end"
          type="date"
          class="date-input"
          placeholder="结束日期"
        />
        <button @click="applyFilters" class="filter-apply-btn">筛选</button>
        <button @click="clearFilters" class="filter-clear-btn">清空</button>
      </div>
    </div>
    
    <!-- 交易列表 -->
    <div v-if="loading && transactions.length === 0" class="loading">
      加载中...
    </div>
    
    <div v-else-if="transactions.length === 0" class="empty-state">
      <div class="empty-icon">📝</div>
      <div class="empty-text">暂无交易记录</div>
      <button @click="navigateToAdd" class="empty-action-btn">开始记账</button>
    </div>
    
    <div v-else class="transaction-list">
      <div
        v-for="transaction in transactions"
        :key="transaction.id"
        class="transaction-item"
        @click="viewTransaction(transaction)"
      >
        <div class="transaction-main">
          <div class="transaction-left">
            <div class="transaction-category">
              {{ getCategory(transaction) }}
            </div>
            <div class="transaction-desc">{{ transaction.description }}</div>
            <div class="transaction-date">{{ formatDate(transaction.date) }}</div>
          </div>
          <div class="transaction-right">
            <div class="transaction-amount" :class="getAmountClass(transaction)">
              {{ formatAmount(transaction) }}
            </div>
          </div>
        </div>
      </div>
      
      <!-- 加载更多 -->
      <div v-if="hasMore" class="load-more">
        <button @click="loadMore" :disabled="loading" class="load-more-btn">
          {{ loading ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTransactionStore } from '../../stores/transaction'
import { type Transaction, type TransactionsQuery } from '../../api/transactions'

const router = useRouter()
const transactionStore = useTransactionStore()

const loading = ref(false)
const currentPage = ref(1)
const perPage = 20

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

function selectTypeFilter(filter: string) {
  currentTypeFilter.value = filter
  currentPage.value = 1
  loadTransactions()
}

function applyFilters() {
  currentPage.value = 1
  loadTransactions()
}

function clearFilters() {
  currentTypeFilter.value = 'all'
  dateRange.value = { start: '', end: '' }
  currentPage.value = 1
  loadTransactions()
}

async function loadTransactions() {
  loading.value = true
  try {
    const query: TransactionsQuery = {
      page: currentPage.value,
      per_page: perPage
    }
    
    if (currentTypeFilter.value !== 'all') {
      query.type = currentTypeFilter.value as any
    }
    
    if (dateRange.value.start) {
      query.start_date = dateRange.value.start
    }
    
    if (dateRange.value.end) {
      query.end_date = dateRange.value.end
    }
    
    await transactionStore.fetchTransactions(query)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  currentPage.value++
  await loadTransactions()
}

function navigateToAdd() {
  router.push('/transactions/add')
}

function viewTransaction(transaction: Transaction) {
  // TODO: 实现交易详情页
  console.log('View transaction:', transaction)
}

function getCategory(transaction: Transaction): string {
  if (transaction.postings.length === 0) return '未分类'
  
  const account = transaction.postings[0].account
  const parts = account.split(':')
  
  if (parts.length >= 2) {
    return parts[parts.length - 1]
  }
  
  return parts[0]
}

function getAmountClass(transaction: Transaction): string {
  if (transaction.postings.length === 0) return ''
  
  const account = transaction.postings[0].account
  if (account.startsWith('Income')) return 'positive'
  if (account.startsWith('Expenses')) return 'negative'
  return ''
}

function formatAmount(transaction: Transaction): string {
  if (transaction.postings.length === 0) return '¥0.00'
  
  const posting = transaction.postings[0]
  const amount = Math.abs(posting.amount)
  const sign = posting.account.startsWith('Income') ? '+' : '-'
  
  return `${sign}¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadTransactions()
})
</script>

<style scoped>
.transactions-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.add-btn {
  padding: 10px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.add-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.filters {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
}

.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.filter-tab {
  flex: 1;
  padding: 8px 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tab.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.date-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
}

.date-separator {
  color: #999;
}

.filter-apply-btn,
.filter-clear-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-apply-btn {
  background: #667eea;
  color: white;
}

.filter-apply-btn:hover {
  background: #5568d3;
}

.filter-clear-btn {
  background: #f5f5f5;
  color: #666;
}

.filter-clear-btn:hover {
  background: #e0e0e0;
}

.loading {
  text-align: center;
  padding: 40px 20px;
  color: #999;
  font-size: 16px;
}

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
  color: #999;
  margin-bottom: 24px;
}

.empty-action-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.empty-action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.transaction-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transaction-item {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.transaction-item:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
  transform: translateY(-1px);
}

.transaction-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.transaction-left {
  flex: 1;
}

.transaction-category {
  display: inline-block;
  padding: 4px 8px;
  background: #f0f0f0;
  color: #666;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 8px;
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
  font-size: 20px;
  font-weight: 700;
}

.transaction-amount.positive {
  color: #4caf50;
}

.transaction-amount.negative {
  color: #f44336;
}

.load-more {
  text-align: center;
  padding: 20px;
}

.load-more-btn {
  padding: 10px 24px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.load-more-btn:hover:not(:disabled) {
  background: #f5f5f5;
}

.load-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
