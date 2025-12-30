<template>
  <div class="recurring-page">
    <div class="page-header">
      <h1>周期任务</h1>
      <button @click="showCreateModal = true" class="create-btn">+ 新建规则</button>
    </div>

    <div v-if="loading && rules.length === 0" class="loading">
      加载中...
    </div>

    <div v-else-if="rules.length === 0" class="empty-state">
      <div class="empty-icon">🔄</div>
      <div class="empty-text">暂无周期任务</div>
      <button @click="showCreateModal = true" class="empty-action-btn">
        创建规则
      </button>
    </div>

    <div v-else class="rules-container">
      <div v-for="rule in rules" :key="rule.id" class="rule-card" :class="{ inactive: !rule.is_active }">
        <div class="rule-header">
          <div class="rule-info">
            <h3 class="rule-name">{{ rule.name }}</h3>
            <span class="rule-frequency">{{ formatFrequency(rule.frequency) }}</span>
            <span v-if="!rule.is_active" class="inactive-badge">已停用</span>
          </div>
          <div class="rule-actions">
            <button @click.stop="toggleRule(rule)" class="toggle-btn">
              {{ rule.is_active ? '停用' : '启用' }}
            </button>
            <button @click.stop="executeRule(rule)" class="execute-btn">
              立即执行
            </button>
          </div>
        </div>

        <div class="rule-details">
          <div class="detail-item">
            <span class="detail-label">频率配置:</span>
            <span class="detail-value">{{ formatFrequencyConfig(rule) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">交易模板:</span>
            <span class="detail-value">{{ rule.transaction_template.description }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">开始日期:</span>
            <span class="detail-value">{{ formatDate(rule.start_date) }}</span>
          </div>
          <div v-if="rule.end_date" class="detail-item">
            <span class="detail-label">结束日期:</span>
            <span class="detail-value">{{ formatDate(rule.end_date) }}</span>
          </div>
        </div>

        <div class="rule-template">
          <div class="template-header">交易明细:</div>
          <div v-for="(posting, index) in rule.transaction_template.postings" :key="index" class="posting-item">
            <span class="posting-account">{{ posting.account }}</span>
            <span class="posting-amount">
              {{ posting.amount > 0 ? '+' : '' }}{{ posting.currency }} {{ posting.amount }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建规则模态框 -->
    <div v-if="showCreateModal" class="modal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>创建周期规则</h3>
          <button @click="showCreateModal = false" class="close-btn">×</button>
        </div>

        <form @submit.prevent="handleCreateRule" class="create-form">
          <div class="form-group">
            <label>规则名称</label>
            <input v-model="newRule.name" type="text" placeholder="例如: 每月房租" required />
          </div>

          <div class="form-group">
            <label>频率类型</label>
            <select v-model="newRule.frequency" required>
              <option value="daily">每日</option>
              <option value="weekly">每周</option>
              <option value="biweekly">双周</option>
              <option value="monthly">每月</option>
              <option value="yearly">每年</option>
            </select>
          </div>

          <!-- 按周配置 -->
          <div v-if="newRule.frequency === 'weekly' || newRule.frequency === 'biweekly'" class="form-group">
            <label>选择星期几（可多选）</label>
            <div class="weekday-selector">
              <label v-for="day in weekdays" :key="day.value" class="weekday-option">
                <input type="checkbox" :value="day.value" v-model="newRule.frequency_config.weekdays" />
                <span>{{ day.label }}</span>
              </label>
            </div>
          </div>

          <!-- 按月配置 -->
          <div v-if="newRule.frequency === 'monthly'" class="form-group">
            <label>选择日期（可多选，-1表示月末）</label>
            <div class="monthday-selector">
              <label v-for="day in 31" :key="day" class="monthday-option">
                <input type="checkbox" :value="day" v-model="newRule.frequency_config.month_days" />
                <span>{{ day }}</span>
              </label>
              <label class="monthday-option">
                <input type="checkbox" :value="-1" v-model="newRule.frequency_config.month_days" />
                <span>月末</span>
              </label>
            </div>
          </div>

          <div class="form-group">
            <label>开始日期</label>
            <input v-model="newRule.start_date" type="date" required />
          </div>

          <div class="form-group">
            <label>结束日期（可选）</label>
            <input v-model="newRule.end_date" type="date" />
          </div>

          <div class="form-group">
            <label>交易描述</label>
            <input v-model="newRule.transaction_template.description" type="text" placeholder="例如: 房租支付" required />
          </div>

          <div class="form-group">
            <label>交易明细</label>
            <div class="postings">
              <div v-for="(posting, index) in newRule.transaction_template.postings" :key="index" class="posting-row">
                <input v-model="posting.account" type="text" placeholder="账户" class="posting-account-input" />
                <input v-model.number="posting.amount" type="number" placeholder="金额" step="0.01"
                  class="posting-amount-input" />
                <select v-model="posting.currency" class="posting-currency-select">
                  <option value="CNY">CNY</option>
                  <option value="USD">USD</option>
                </select>
                <button type="button" @click="removePosting(index)" class="remove-posting-btn">
                  ×
                </button>
              </div>
            </div>
            <button type="button" @click="addPosting" class="add-posting-btn">
              + 添加明细
            </button>
          </div>

          <div v-if="createError" class="error-message">
            {{ createError }}
          </div>

          <div class="form-actions">
            <button type="button" @click="showCreateModal = false" class="cancel-btn">
              取消
            </button>
            <button type="submit" :disabled="creatingRule" class="submit-btn">
              {{ creatingRule ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { recurringApi, type RecurringRule, type CreateRecurringRuleRequest } from '../../api/recurring'

const loading = ref(false)
const rules = ref<RecurringRule[]>([])

const showCreateModal = ref(false)
const newRule = ref<CreateRecurringRuleRequest>({
  name: '',
  frequency: 'monthly',
  frequency_config: {
    weekdays: [],
    month_days: []
  },
  transaction_template: {
    description: '',
    postings: [
      { account: '', amount: 0, currency: 'CNY' },
      { account: '', amount: 0, currency: 'CNY' }
    ]
  },
  start_date: new Date().toISOString().split('T')[0] ?? '',
  end_date: '',
  is_active: true
})
const creatingRule = ref(false)
const createError = ref('')

const weekdays = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatFrequency(frequency: string): string {
  const frequencies: Record<string, string> = {
    daily: '每日',
    weekly: '每周',
    biweekly: '双周',
    monthly: '每月',
    yearly: '每年'
  }
  return frequencies[frequency] || frequency
}

function formatFrequencyConfig(rule: RecurringRule): string {
  if (rule.frequency === 'daily') {
    return '每天'
  } else if (rule.frequency === 'weekly' || rule.frequency === 'biweekly') {
    if (!rule.frequency_config.weekdays || rule.frequency_config.weekdays.length === 0) {
      return '未配置'
    }
    const days = rule.frequency_config.weekdays.map(d => {
      const day = weekdays.find(w => w.value === d)
      return day ? day.label : d
    })
    return days.join(', ')
  } else if (rule.frequency === 'monthly') {
    if (!rule.frequency_config.month_days || rule.frequency_config.month_days.length === 0) {
      return '未配置'
    }
    const days = rule.frequency_config.month_days.map(d => d === -1 ? '月末' : `${d}日`)
    return days.join(', ')
  } else if (rule.frequency === 'yearly') {
    return '每年一次'
  }
  return '未配置'
}

async function loadRules() {
  loading.value = true
  try {
    rules.value = await recurringApi.getRules()
  } catch (error) {
    console.error('Failed to load recurring rules:', error)
  } finally {
    loading.value = false
  }
}

async function toggleRule(rule: RecurringRule) {
  try {
    await recurringApi.updateRule(rule.id, {
      is_active: !rule.is_active
    })
    rule.is_active = !rule.is_active
  } catch (error) {
    console.error('Failed to toggle rule:', error)
  }
}

async function executeRule(rule: RecurringRule) {
  try {
    const today = new Date().toISOString().split('T')[0] ?? ''
    await recurringApi.executeRule(rule.id, today)
    alert(`规则 "${rule.name}" 已执行`)
  } catch (error: any) {
    alert(`执行失败: ${error.message}`)
  }
}

function addPosting() {
  newRule.value.transaction_template.postings.push({
    account: '',
    amount: 0,
    currency: 'CNY'
  })
}

function removePosting(index: number) {
  newRule.value.transaction_template.postings.splice(index, 1)
}

async function handleCreateRule() {
  if (!newRule.value.name || !newRule.value.start_date) {
    createError.value = '请填写所有必填字段'
    return
  }

  if (newRule.value.transaction_template.postings.length < 2) {
    createError.value = '至少需要两条交易明细'
    return
  }

  creatingRule.value = true
  createError.value = ''

  try {
    await recurringApi.createRule({
      ...newRule.value,
      end_date: newRule.value.end_date || undefined
    })

    // Reload rules
    await loadRules()

    // Close modal and reset form
    showCreateModal.value = false
    resetForm()
  } catch (err: any) {
    createError.value = err.message || '创建失败，请重试'
  } finally {
    creatingRule.value = false
  }
}

function resetForm() {
  newRule.value = {
    name: '',
    frequency: 'monthly',
    frequency_config: {
      weekdays: [],
      month_days: []
    },
    transaction_template: {
      description: '',
      postings: [
        { account: '', amount: 0, currency: 'CNY' },
        { account: '', amount: 0, currency: 'CNY' }
      ]
    },
    start_date: new Date().toISOString().split('T')[0] ?? '',
    end_date: '',
    is_active: true
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.recurring-page {
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

.rules-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rule-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 20px;
  transition: all 0.2s;
}

.rule-card.inactive {
  opacity: 0.6;
}

.rule-card:not(.inactive):hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.rule-info {
  flex: 1;
}

.rule-name {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
}

.rule-frequency {
  display: inline-block;
  padding: 4px 8px;
  background: #e3f2fd;
  color: #1976d2;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 8px;
}

.inactive-badge {
  display: inline-block;
  padding: 4px 8px;
  background: #ffebee;
  color: #f44336;
  border-radius: 4px;
  font-size: 12px;
}

.rule-actions {
  display: flex;
  gap: 8px;
}

.toggle-btn,
.execute-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn {
  background: #f5f5f5;
  color: #666;
}

.toggle-btn:hover {
  background: #e0e0e0;
}

.execute-btn {
  background: #667eea;
  color: white;
}

.execute-btn:hover {
  background: #5568d3;
}

.rule-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.detail-label {
  color: #999;
  min-width: 80px;
}

.detail-value {
  color: #333;
  font-weight: 500;
}

.rule-template {
  background: #f9f9f9;
  border-radius: 8px;
  padding: 12px;
}

.template-header {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.posting-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.posting-item:last-child {
  border-bottom: none;
}

.posting-account {
  color: #333;
}

.posting-amount {
  font-weight: 600;
  color: #667eea;
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

.weekday-selector,
.monthday-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.weekday-option,
.monthday-option {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.weekday-option:hover,
.monthday-option:hover {
  background: #f5f5f5;
}

.weekday-option input:checked+span,
.monthday-option input:checked+span {
  font-weight: 600;
  color: #667eea;
}

.postings {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.posting-row {
  display: grid;
  grid-template-columns: 2fr 1fr 80px 40px;
  gap: 8px;
  align-items: center;
}

.posting-account-input,
.posting-amount-input,
.posting-currency-select {
  padding: 8px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 13px;
}

.remove-posting-btn {
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

.remove-posting-btn:hover {
  background: #f44336;
  color: white;
}

.add-posting-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: 1px dashed #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.add-posting-btn:hover {
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
