<template>
  <div class="budgets-page">
    <div class="page-header">
      <h1>预算管理</h1>
      <button @click="showCreateModal = true" class="create-btn">+ 新建预算</button>
    </div>
    
    <div v-if="loading && budgets.length === 0" class="loading">
      加载中...
    </div>
    
    <div v-else-if="budgets.length === 0" class="empty-state">
      <div class="empty-icon">🎯</div>
      <div class="empty-text">暂无预算</div>
      <button @click="showCreateModal = true" class="empty-action-btn">
        创建预算
      </button>
    </div>
    
    <div v-else class="budgets-container">
      <div
        v-for="budget in budgets"
        :key="budget.id"
        class="budget-card"
        @click="viewBudgetDetail(budget)"
      >
        <div class="budget-header">
          <div class="budget-info">
            <h3 class="budget-name">{{ budget.name }}</h3>
            <span class="budget-period">{{ formatPeriodType(budget.period_type) }}</span>
          </div>
          <button @click.stop="loadExecution(budget.id)" class="refresh-btn">
            刷新
          </button>
        </div>
        
        <div v-if="executions[budget.id]" class="budget-execution">
          <div class="execution-summary">
            <div class="summary-item">
              <span class="label">预算总额</span>
              <span class="value">¥{{ formatNumber(executions[budget.id].total_budget) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">实际支出</span>
              <span class="value">¥{{ formatNumber(executions[budget.id].total_actual) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">剩余额度</span>
              <span class="value" :class="getRemainingClass(executions[budget.id])">
                ¥{{ formatNumber(executions[budget.id].total_remaining) }}
              </span>
            </div>
          </div>
          
          <div class="progress-bar">
            <div
              class="progress-fill"
              :class="getStatusClass(executions[budget.id].status)"
              :style="{ width: getProgressWidth(executions[budget.id]) + '%' }"
            ></div>
          </div>
          
          <div class="status-badge" :class="getStatusClass(executions[budget.id].status)">
            {{ getStatusText(executions[budget.id].status) }}
          </div>
        </div>
        
        <div class="budget-period-info">
          <span>{{ formatDate(budget.start_date) }}</span>
          <span v-if="budget.end_date"> - {{ formatDate(budget.end_date) }}</span>
        </div>
      </div>
    </div>
    
    <!-- 创建预算模态框 -->
    <div v-if="showCreateModal" class="modal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>创建预算</h3>
          <button @click="showCreateModal = false" class="close-btn">×</button>
        </div>
        
        <form @submit.prevent="handleCreateBudget" class="create-form">
          <div class="form-group">
            <label>预算名称</label>
            <input
              v-model="newBudget.name"
              type="text"
              placeholder="例如: 2024年1月预算"
              required
            />
          </div>
          
          <div class="form-group">
            <label>周期类型</label>
            <select v-model="newBudget.period_type" required>
              <option value="monthly">月度</option>
              <option value="quarterly">季度</option>
              <option value="yearly">年度</option>
            </select>
          </div>
          
          <div class="form-group">
            <label>开始日期</label>
            <input v-model="newBudget.start_date" type="date" required />
          </div>
          
          <div class="form-group">
            <label>结束日期（可选）</label>
            <input v-model="newBudget.end_date" type="date" />
          </div>
          
          <div class="form-group">
            <label>预算项目</label>
            <div class="budget-items">
              <div
                v-for="(item, index) in newBudget.items"
                :key="index"
                class="budget-item-row"
              >
                <input
                  v-model="item.account_pattern"
                  type="text"
                  placeholder="账户模式（如: Expenses:Food:*）"
                  class="item-account"
                />
                <input
                  v-model.number="item.amount"
                  type="number"
                  placeholder="金额"
                  step="0.01"
                  min="0"
                  class="item-amount"
                />
                <select v-model="item.currency" class="item-currency">
                  <option value="CNY">CNY</option>
                  <option value="USD">USD</option>
                </select>
                <button
                  type="button"
                  @click="removeBudgetItem(index)"
                  class="remove-item-btn"
                >
                  ×
                </button>
              </div>
            </div>
            <button type="button" @click="addBudgetItem" class="add-item-btn">
              + 添加项目
            </button>
          </div>
          
          <div v-if="createError" class="error-message">
            {{ createError }}
          </div>
          
          <div class="form-actions">
            <button type="button" @click="showCreateModal = false" class="cancel-btn">
              取消
            </button>
            <button type="submit" :disabled="creatingBudget" class="submit-btn">
              {{ creatingBudget ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { budgetsApi, type Budget, type BudgetExecution } from '../../api/budgets'

const loading = ref(false)
const budgets = ref<Budget[]>([])
const executions = reactive<Record<number, BudgetExecution>>({})

const showCreateModal = ref(false)
const newBudget = ref({
  name: '',
  period_type: 'monthly' as 'monthly' | 'quarterly' | 'yearly',
  start_date: new Date().toISOString().split('T')[0],
  end_date: '',
  items: [
    { account_pattern: '', amount: 0, currency: 'CNY' }
  ]
})
const creatingBudget = ref(false)
const createError = ref('')

function formatNumber(num: number): string {
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate (dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatPeriodType(type: string): string {
  const types = {
    monthly: '月度',
    quarterly: '季度',
    yearly: '年度'
  }
  return types[type as keyof typeof types] || type
}

function getProgressWidth(execution: BudgetExecution): number {
  if (execution.total_budget === 0) return 0
  return Math.min((execution.total_actual / execution.total_budget) * 100, 100)
}

function getStatusClass(status: string): string {
  const classes = {
    normal: 'status-normal',
    warning: 'status-warning',
    exceeded: 'status-exceeded'
  }
  return classes[status as keyof typeof classes] || ''
}

function getStatusText(status: string): string {
  const texts = {
    normal: '正常',
    warning: '警告',
    exceeded: '超支'
  }
  return texts[status as keyof typeof texts] || status
}

function getRemainingClass(execution: BudgetExecution): string {
  if (execution.total_remaining < 0) return 'negative'
  if (execution.total_remaining < execution.total_budget * 0.2) return 'warning'
  return 'positive'
}

async function loadBudgets() {
  loading.value = true
  try {
    budgets.value = await budgetsApi.getBudgets()
    // Load execution for each budget
    for (const budget of budgets.value) {
      await loadExecution(budget.id)
    }
  } catch (error) {
    console.error('Failed to load budgets:', error)
  } finally {
    loading.value = false
  }
}

async function loadExecution(budgetId: number) {
  try {
    const execution = await budgetsApi.getBudgetExecution(budgetId)
    executions[budgetId] = execution
  } catch (error) {
    console.error('Failed to load budget execution:', error)
  }
}

function viewBudgetDetail(budget: Budget) {
  console.log('View budget detail:', budget)
  // TODO: 实现预算详情页
}

function addBudgetItem() {
  newBudget.value.items.push({
    account_pattern: '',
    amount: 0,
    currency: 'CNY'
  })
}

function removeBudgetItem(index: number) {
  newBudget.value.items.splice(index, 1)
}

async function handleCreateBudget() {
  if (!newBudget.value.name || !newBudget.value.start_date) {
    createError.value = '请填写所有必填字段'
    return
  }
  
  if (newBudget.value.items.length === 0) {
    createError.value = '请至少添加一个预算项目'
    return
  }
  
  creatingBudget.value = true
  createError.value = ''
  
  try {
    await budgetsApi.createBudget({
      name: newBudget.value.name,
      period_type: newBudget.value.period_type,
      start_date: newBudget.value.start_date,
      end_date: newBudget.value.end_date || undefined,
      items: newBudget.value.items.filter(item => item.account_pattern && item.amount > 0)
    })
    
    // Reload budgets
    await loadBudgets()
    
    // Close modal and reset form
    showCreateModal.value = false
    newBudget.value = {
      name: '',
      period_type: 'monthly',
      start_date: new Date().toISOString().split('T')[0],
      end_date: '',
      items: [{ account_pattern: '', amount: 0, currency: 'CNY' }]
    }
  } catch (err: any) {
    createError.value = err.message || '创建失败，请重试'
  } finally {
    creatingBudget.value = false
  }
}

onMounted(() => {
  loadBudgets()
})
</script>

<style scoped>
.budgets-page {
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

.create-btn {
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

.create-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
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

.budgets-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.budget-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.budget-card:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
  transform: translateY(-2px);
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.budget-info {
  flex: 1;
}

.budget-name {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.budget-period {
  display: inline-block;
  padding: 4px 8px;
  background: #f0f0f0;
  color: #666;
  border-radius: 4px;
  font-size: 12px;
}

.refresh-btn {
  padding: 6px 12px;
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background: #e0e0e0;
}

.budget-execution {
  margin-bottom: 16px;
}

.execution-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-item .label {
  font-size: 12px;
  color: #999;
}

.summary-item .value {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.summary-item .value.positive {
  color: #4caf50;
}

.summary-item .value.warning {
  color: #ff9800;
}

.summary-item .value.negative {
  color: #f44336;
}

.progress-bar {
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s;
}

.progress-fill.status-normal {
  background: linear-gradient(90deg, #4caf50, #66bb6a);
}

.progress-fill.status-warning {
  background: linear-gradient(90deg, #ff9800, #ffa726);
}

.progress-fill.status-exceeded {
  background: linear-gradient(90deg, #f44336, #ef5350);
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.status-normal {
  background: #e8f5e9;
  color: #4caf50;
}

.status-badge.status-warning {
  background: #fff3e0;
  color: #ff9800;
}

.status-badge.status-exceeded {
  background: #ffebee;
  color: #f44336;
}

.budget-period-info {
  font-size: 12px;
  color: #999;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

/* Modal styles */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 32px;
  color: #999;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}

.close-btn:hover {
  color: #333;
}

.create-form {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-group input,
.form-group select {
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.budget-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.budget-item-row {
  display: grid;
  grid-template-columns: 2fr 1fr 80px 40px;
  gap: 8px;
  align-items: center;
}

.item-account,
.item-amount,
.item-currency {
  padding: 8px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 13px;
}

.remove-item-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: #ffebee;
  color: #f44336;
  border: none;
  border-radius: 6px;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.remove-item-btn:hover {
  background: #f44336;
  color: white;
}

.add-item-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: 1px dashed #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.add-item-btn:hover {
  background: #e0e0e0;
}

.error-message {
  padding: 12px 16px;
  background: #fee;
  color: #c33;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.cancel-btn,
.submit-btn {
  flex: 1;
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn {
  background: #f5f5f5;
  color: #666;
}

.cancel-btn:hover {
  background: #e0e0e0;
}

.submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
