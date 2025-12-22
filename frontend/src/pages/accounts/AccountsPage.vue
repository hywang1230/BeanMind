<template>
  <div class="accounts-page">
    <div class="page-header">
      <h1>账户管理</h1>
      <button @click="showCreateModal = true" class="create-btn">+ 新建账户</button>
    </div>
    
    <div v-if="loading && accounts.length === 0" class="loading">
      加载中...
    </div>
    
    <div v-else-if="accounts.length === 0" class="empty-state">
      <div class="empty-icon">💰</div>
      <div class="empty-text">暂无账户</div>
      <button @click="showCreateModal = true" class="empty-action-btn">
        创建账户
      </button>
    </div>
    
    <div v-else class="accounts-container">
      <!-- 按类型分组显示账户 -->
      <div
        v-for="type in accountTypes"
        :key="type.value"
        class="account-type-section"
      >
        <div class="type-header">
          <h2 class="type-title">{{ type.label }}</h2>
        </div>
        
        <div class="account-list">
          <div
            v-for="account in getAccountsByType(type.value)"
            :key="account.name"
            class="account-card"
            @click="viewAccountDetail(account)"
          >
            <div class="account-info">
              <div class="account-name">{{ account.name }}</div>
              <div class="account-currencies">
                {{ account.currencies.join(', ') }}
              </div>
            </div>
            <div class="account-balance">
              <button
                @click.stop="loadBalance(account)"
                class="balance-btn"
                :disabled="loadingBalance[account.name]"
              >
                {{ loadingBalance[account.name] ? '加载中...' : '查看余额' }}
              </button>
              <div
                v-if="balances[account.name]"
                class="balance-amount"
              >
                {{ formatBalance(balances[account.name]) }}
              </div>
            </div>
            
            <!-- 子账户 -->
            <div
              v-if="account.children && account.children.length > 0"
              class="sub-accounts"
              @click.stop
            >
              <div
                v-for="child in account.children"
                :key="child.name"
                class="sub-account-item"
                @click="viewAccountDetail(child)"
              >
                <div class="sub-account-info">
                  <div class="sub-account-name">{{ getShortName(child.name) }}</div>
                  <div class="sub-account-currencies">
                    {{ child.currencies.join(', ') }}
                  </div>
                </div>
                <div class="sub-account-balance">
                  <button
                    @click.stop="loadBalance(child)"
                    class="balance-btn small"
                    :disabled="loadingBalance[child.name]"
                  >
                    {{ loadingBalance[child.name] ? '...' : '余额' }}
                  </button>
                  <div
                    v-if="balances[child.name]"
                    class="balance-amount small"
                  >
                    {{ formatBalance(balances[child.name]) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 创建账户模态框 -->
    <div v-if="showCreateModal" class="modal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>创建账户</h3>
          <button @click="showCreateModal = false" class="close-btn">×</button>
        </div>
        
        <form @submit.prevent="handleCreateAccount" class="create-form">
          <div class="form-group">
            <label>账户名称</label>
            <input
              v-model="newAccount.name"
              type="text"
              placeholder="例如: Assets:Bank:ICBC"
              required
            />
          </div>
          
          <div class="form-group">
            <label>账户类型</label>
            <select v-model="newAccount.type" required>
              <option v-for="type in accountTypes" :key="type.value" :value="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>支持币种</label>
            <input
              v-model="newAccount.currencies"
              type="text"
              placeholder="例如: CNY,USD（逗号分隔）"
            />
          </div>
          
          <div v-if="createError" class="error-message">
            {{ createError }}
          </div>
          
          <div class="form-actions">
            <button type="button" @click="showCreateModal = false" class="cancel-btn">
              取消
            </button>
            <button type="submit" :disabled="creatingAccount" class="submit-btn">
              {{ creatingAccount ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { accountsApi, type Account, type Balance } from '../../api/accounts'

const accountTypes = [
  { value: 'Assets', label: '资产' },
  { value: 'Liabilities', label: '负债' },
  { value: 'Equity', label: '权益' },
  { value: 'Income', label: '收入' },
  { value: 'Expenses', label: '支出' }
]

const loading = ref(false)
const accounts = ref<Account[]>([])
const balances = reactive<Record<string, Balance[]>>({})
const loadingBalance = reactive<Record<string, boolean>>({})

const showCreateModal = ref(false)
const newAccount = ref({
  name: '',
  type: 'Assets',
  currencies: 'CNY'
})
const creatingAccount = ref(false)
const createError = ref('')

function getAccountsByType(type: string): Account[] {
  return accounts.value.filter(acc => acc.account_type === type)
}

function getShortName(fullName: string): string {
  const parts = fullName.split(':')
  return parts[parts.length - 1]
}

async function loadAccounts() {
  loading.value = true
  try {
    accounts.value = await accountsApi.getAccounts()
  } catch (error) {
    console.error('Failed to load accounts:', error)
  } finally {
    loading.value = false
  }
}

async function loadBalance(account: Account) {
  loadingBalance[account.name] = true
  try {
    const balance = await accountsApi.getBalance(account.name)
    balances[account.name] = balance
  } catch (error) {
    console.error('Failed to load balance:', error)
  } finally {
    loadingBalance[account.name] = false
  }
}

function formatBalance(balanceList: Balance[]): string {
  if (!balanceList || balanceList.length === 0) return '¥0.00'
  
  return balanceList
    .map(b => `${b.currency} ${b.amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
    .join(', ')
}

function viewAccountDetail(account: Account) {
  console.log('View account detail:', account)
  // TODO: 实现账户详情页
}

async function handleCreateAccount() {
  if (!newAccount.value.name || !newAccount.value.type) {
    createError.value = '请填写所有必填字段'
    return
  }
  
  creatingAccount.value = true
  createError.value = ''
  
  try {
    const currencies = newAccount.value.currencies
      .split(',')
      .map(c => c.trim())
      .filter(c => c)
    
    await accountsApi.createAccount({
      name: newAccount.value.name,
      type: newAccount.value.type,
      currencies: currencies.length > 0 ? currencies : undefined
    })
    
    // 重新加载账户列表
    await loadAccounts()
    
    // 关闭模态框并重置表单
    showCreateModal.value = false
    newAccount.value = {
      name: '',
      type: 'Assets',
      currencies: 'CNY'
    }
  } catch (err: any) {
    createError.value = err.message || '创建失败，请重试'
  } finally {
    creatingAccount.value = false
  }
}

onMounted(() => {
  loadAccounts()
})
</script>

<style scoped>
.accounts-page {
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

.accounts-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.account-type-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e0e0e0;
}

.type-header {
  margin-bottom: 16px;
}

.type-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.account-card {
  padding: 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.account-card:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

.account-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.account-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.account-currencies {
  font-size: 12px;
  color: #999;
}

.account-balance {
  display: flex;
  align-items: center;
  gap: 12px;
}

.balance-btn {
  padding: 6px 12px;
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.balance-btn:hover:not(:disabled) {
  background: #e0e0e0;
}

.balance-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.balance-btn.small {
  padding: 4px 8px;
  font-size: 11px;
}

.balance-amount {
  font-size: 16px;
  font-weight: 600;
  color: #667eea;
}

.balance-amount.small {
  font-size: 14px;
}

.sub-accounts {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sub-account-item {
  padding: 12px;
  background: #f9f9f9;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s;
}

.sub-account-item:hover {
  background: #f0f0f0;
}

.sub-account-info {
  flex: 1;
}

.sub-account-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.sub-account-currencies {
  font-size: 11px;
  color: #999;
}

.sub-account-balance {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 模态框样式 */
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
  max-width: 500px;
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
