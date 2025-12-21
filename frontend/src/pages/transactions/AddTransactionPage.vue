<template>
  <div class="add-transaction-page">
    <div class="page-header">
      <button @click="goBack" class="back-btn">← 返回</button>
      <h1>记一笔</h1>
      <div class="header-spacer"></div>
    </div>
    
    <form @submit.prevent="handleSubmit" class="transaction-form">
      <!-- 交易类型 -->
      <div class="form-section">
        <div class="type-tabs">
          <button
            v-for="type in transactionTypes"
            :key="type.value"
            type="button"
            @click="selectType(type.value)"
            class="type-tab"
            :class="{ active: formData.type === type.value }"
          >
            {{ type.label }}
          </button>
        </div>
      </div>
      
      <!-- 金额输入 -->
      <div class="form-section">
        <label class="form-label">金额</label>
        <AmountInput
          v-model="formData.amount"
          :currency="formData.currency"
          placeholder="请输入金额"
        />
      </div>
      
      <!-- 分类选择 -->
      <div v-if="formData.type !== 'transfer'" class="form-section">
        <label class="form-label">分类</label>
        <CategoryPicker
          v-model="formData.category"
          :type="formData.type"
        />
      </div>
      
      <!-- 账户选择 -->
      <div class="form-section">
        <label class="form-label">
          {{ formData.type === 'transfer' ? '转出账户' : '账户' }}
        </label>
        <AccountPicker
          v-model="formData.fromAccount"
          :account-type="formData.type === 'income' ? 'Assets' : undefined"
          placeholder="选择账户"
        />
      </div>
      
      <!-- 转账目标账户 -->
      <div v-if="formData.type === 'transfer'" class="form-section">
        <label class="form-label">转入账户</label>
        <AccountPicker
          v-model="formData.toAccount"
          account-type="Assets"
          placeholder="选择账户"
        />
      </div>
      
      <!-- 日期 -->
      <div class="form-section">
        <label class="form-label">日期</label>
        <input
          v-model="formData.date"
          type="date"
          class="form-input"
          required
        />
      </div>
      
      <!-- 备注 -->
      <div class="form-section">
        <label class="form-label">备注</label>
        <input
          v-model="formData.description"
          type="text"
          class="form-input"
          placeholder="添加备注（可选）"
        />
      </div>
      
      <!-- 标签 -->
      <div class="form-section">
        <label class="form-label">标签</label>
        <div class="tags-input">
          <div class="tag-list">
            <span
              v-for="(tag, index) in formData.tags"
              :key="index"
              class="tag"
            >
              {{ tag }}
              <button
                type="button"
                @click="removeTag(index)"
                class="tag-remove"
              >
                ×
              </button>
            </span>
          </div>
          <input
            v-model="newTag"
            type="text"
            class="tag-input"
            placeholder="添加标签"
            @keyup.enter="addTag"
          />
        </div>
      </div>
      
      <!-- 错误消息 -->
      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      
      <!-- 提交按钮 -->
      <button
        type="submit"
        class="submit-btn"
        :disabled="loading || !isFormValid"
      >
        {{ loading ? '保存中...' : '保存' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTransactionStore } from '../../stores/transaction'
import { type CreateTransactionRequest, type Posting } from '../../api/transactions'
import AmountInput from '../../components/AmountInput.vue'
import CategoryPicker from '../../components/CategoryPicker.vue'
import AccountPicker from '../../components/AccountPicker.vue'

const router = useRouter()
const transactionStore = useTransactionStore()

const transactionTypes = [
  { value: 'expense', label: '支出' },
  { value: 'income', label: '收入' },
  { value: 'transfer', label: '转账' }
]

const formData = ref({
  type: 'expense' as 'expense' | 'income' | 'transfer',
  amount: 0,
  currency: 'CNY',
  category: '',
  fromAccount: '',
  toAccount: '',
  date: new Date().toISOString().split('T')[0],
  description: '',
  tags: [] as string[]
})

const newTag = ref('')
const loading = ref(false)
const error = ref('')

const isFormValid = computed(() => {
  if (formData.value.amount <= 0) return false
  if (!formData.value.date) return false
  if (!formData.value.fromAccount) return false
  
  if (formData.value.type === 'transfer') {
    return !!formData.value.toAccount
  } else {
    return !!formData.value.category
  }
})

function selectType(type: 'expense' | 'income' | 'transfer') {
  formData.value.type = type
  formData.value.category = ''
  formData.value.fromAccount = ''
  formData.value.toAccount = ''
}

function addTag() {
  if (newTag.value.trim() && !formData.value.tags.includes(newTag.value.trim())) {
    formData.value.tags.push(newTag.value.trim())
    newTag.value = ''
  }
}

function removeTag(index: number) {
  formData.value.tags.splice(index, 1)
}

function buildPostings(): Posting[] {
  const postings: Posting[] = []
  
  if (formData.value.type === 'expense') {
    // 支出：从资产账户扣除，增加支出账户
    postings.push({
      account: formData.value.category,
      amount: formData.value.amount,
      currency: formData.value.currency
    })
    postings.push({
      account: formData.value.fromAccount,
      amount: -formData.value.amount,
      currency: formData.value.currency
    })
  } else if (formData.value.type === 'income') {
    // 收入：增加资产账户，增加收入账户（负数）
    postings.push({
      account: formData.value.fromAccount,
      amount: formData.value.amount,
      currency: formData.value.currency
    })
    postings.push({
      account: formData.value.category,
      amount: -formData.value.amount,
      currency: formData.value.currency
    })
  } else if (formData.value.type === 'transfer') {
    // 转账：从一个账户转到另一个账户
    postings.push({
      account: formData.value.fromAccount,
      amount: -formData.value.amount,
      currency: formData.value.currency
    })
    postings.push({
      account: formData.value.toAccount,
      amount: formData.value.amount,
      currency: formData.value.currency
    })
  }
  
  return postings
}

async function handleSubmit() {
  if (!isFormValid.value) {
    error.value = '请填写所有必填字段'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const request: CreateTransactionRequest = {
      date: formData.value.date,
      description: formData.value.description || `${transactionTypes.find(t => t.value === formData.value.type)?.label}`,
      postings: buildPostings(),
      tags: formData.value.tags.length > 0 ? formData.value.tags : undefined
    }
    
    await transactionStore.createTransaction(request)
    
    // 成功后返回列表页
    router.push('/transactions')
  } catch (err: any) {
    error.value = err.message || '保存失败，请重试'
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.back()
}
</script>

<style scoped>
.add-transaction-page {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  margin: 0;
}

.back-btn {
  padding: 8px 12px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #f5f5f5;
}

.header-spacer {
  width: 80px;
}

.transaction-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.type-tabs {
  display: flex;
  gap: 8px;
}

.type-tab {
  flex: 1;
  padding: 12px 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.type-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
}

.form-input {
  padding: 12px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #667eea;
}

.tags-input {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: white;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #e0e0e0;
  border-radius: 4px;
  font-size: 14px;
  color: #333;
}

.tag-remove {
  background: none;
  border: none;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  color: #999;
  padding: 0;
}

.tag-remove:hover {
  color: #333;
}

.tag-input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 14px;
  padding: 4px 0;
}

.error-message {
  padding: 12px 16px;
  background: #fee;
  color: #c33;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.submit-btn {
  padding: 14px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
