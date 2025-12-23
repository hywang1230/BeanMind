<template>
  <f7-page name="transaction-detail">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>交易详情</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="editTransaction">
          <f7-icon ios="f7:pencil" md="material:edit" />
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <f7-preloader></f7-preloader>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
      <f7-button fill round @click="loadTransaction" class="retry-btn">
        重试
      </f7-button>
    </div>

    <!-- 详情内容 -->
    <div v-else-if="transaction" class="detail-content">
      <!-- 金额卡片 -->
      <div class="amount-card" :class="getTypeClass()">
        <div class="type-icon">
          <f7-icon :ios="getTypeIcon()" size="32"></f7-icon>
        </div>
        <div class="amount-display" :class="getAmountClass()">
          {{ formatTotalAmount() }}
        </div>
        <div class="type-label">{{ getTypeLabel() }}</div>
      </div>

      <!-- 基本信息 -->
      <f7-list strong-ios dividers-ios inset class="info-list">
        <f7-list-item title="日期" :after="formatDate(transaction.date)">
          <template #media>
            <i class="icon f7-icons">calendar</i>
          </template>
        </f7-list-item>

        <f7-list-item v-if="transaction.payee" title="交易方" :after="transaction.payee">
          <template #media>
            <i class="icon f7-icons">person_2_fill</i>
          </template>
        </f7-list-item>

        <f7-list-item v-if="transaction.description" title="备注">
          <template #media>
            <i class="icon f7-icons">pencil_circle</i>
          </template>
          <template #after>
            <span class="description-text">{{ transaction.description }}</span>
          </template>
        </f7-list-item>

        <f7-list-item v-if="transaction.tags && transaction.tags.length > 0" title="标签">
          <template #media>
            <i class="icon f7-icons">tag_fill</i>
          </template>
          <template #after>
            <div class="tags-container">
              <span v-for="tag in transaction.tags" :key="tag" class="tag-chip">
                {{ tag }}
              </span>
            </div>
          </template>
        </f7-list-item>
      </f7-list>

      <!-- 账户分录 -->
      <div class="section-header">账户分录</div>
      <f7-list strong-ios dividers-ios inset class="postings-list">
        <f7-list-item
          v-for="(posting, index) in transaction.postings"
          :key="index"
          :title="formatAccountName(posting.account)"
          :subtitle="posting.account"
        >
          <template #media>
            <div class="posting-icon" :class="getPostingIconClass(posting)">
              <f7-icon :ios="getPostingIcon(posting)" size="18"></f7-icon>
            </div>
          </template>
          <template #after>
            <span class="posting-amount" :class="getPostingAmountClass(posting)">
              {{ formatPostingAmount(posting) }}
            </span>
          </template>
        </f7-list-item>
      </f7-list>

      <!-- 元数据 -->
      <div class="section-header">其他信息</div>
      <f7-list strong-ios dividers-ios inset class="meta-list">
        <f7-list-item title="交易ID">
          <template #media>
            <i class="icon f7-icons">number</i>
          </template>
          <template #after>
            <span class="id-text">{{ transaction.id }}</span>
          </template>
        </f7-list-item>

        <f7-list-item v-if="transaction.created_at" title="创建时间" :after="formatDateTime(transaction.created_at)">
          <template #media>
            <i class="icon f7-icons">clock</i>
          </template>
        </f7-list-item>

        <f7-list-item v-if="transaction.updated_at" title="更新时间" :after="formatDateTime(transaction.updated_at)">
          <template #media>
            <i class="icon f7-icons">arrow_clockwise</i>
          </template>
        </f7-list-item>
      </f7-list>

      <!-- 删除按钮 -->
      <f7-block>
        <f7-button large fill color="red" @click="confirmDelete">
          删除交易
        </f7-button>
      </f7-block>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { f7 } from 'framework7-vue'
import { transactionsApi, type Transaction, type Posting } from '../../api/transactions'
import { useUIStore } from '../../stores/ui'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()

const loading = ref(true)
const error = ref('')
const transaction = ref<Transaction | null>(null)

function goBack() {
  router.back()
}

function editTransaction() {
  if (transaction.value) {
    router.push(`/transactions/${transaction.value.id}/edit`)
  }
}

async function loadTransaction() {
  const id = route.params.id as string
  if (!id) {
    error.value = '无效的交易ID'
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''

  try {
    transaction.value = await transactionsApi.getTransaction(id)
  } catch (e: any) {
    console.error('Failed to load transaction:', e)
    error.value = e.message || '加载交易详情失败'
  } finally {
    loading.value = false
  }
}

function getTypeClass(): string {
  const type = transaction.value?.transaction_type
  if (type === 'income') return 'income-card'
  if (type === 'expense') return 'expense-card'
  if (type === 'transfer') return 'transfer-card'
  return ''
}

function getTypeIcon(): string {
  const type = transaction.value?.transaction_type
  if (type === 'income') return 'f7:arrow_down_circle_fill'
  if (type === 'expense') return 'f7:arrow_up_circle_fill'
  if (type === 'transfer') return 'f7:arrow_right_arrow_left_circle_fill'
  return 'f7:doc_text_fill'
}

function getTypeLabel(): string {
  const type = transaction.value?.transaction_type
  if (type === 'income') return '收入'
  if (type === 'expense') return '支出'
  if (type === 'transfer') return '转账'
  if (type === 'opening') return '期初'
  return '其他'
}

function getAmountClass(): string {
  const type = transaction.value?.transaction_type
  if (type === 'income') return 'positive'
  if (type === 'expense') return 'negative'
  return 'neutral'
}

function formatTotalAmount(): string {
  if (!transaction.value || transaction.value.postings.length === 0) return '¥0.00'
  
  const posting = transaction.value.postings[0]!
  const amount = Math.abs(Number(posting.amount))
  const currency = posting.currency || 'CNY'
  const symbol = getCurrencySymbol(currency)
  
  const sign = transaction.value.transaction_type === 'income' ? '+' : 
               transaction.value.transaction_type === 'expense' ? '-' : ''
  
  return `${sign}${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function getCurrencySymbol(currency: string): string {
  const symbols: Record<string, string> = {
    'CNY': '¥',
    'USD': '$',
    'HKD': 'HK$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥'
  }
  return symbols[currency] || currency + ' '
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekDay = weekDays[date.getDay()]
  
  return `${year}年${month}月${day}日 ${weekDay}`
}

function formatDateTime(dateTimeStr: string): string {
  const date = new Date(dateTimeStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function formatAccountName(account: string): string {
  return account
}

function getPostingIcon(posting: Posting): string {
  if (posting.account.startsWith('Income')) return 'f7:arrow_down'
  if (posting.account.startsWith('Expenses')) return 'f7:arrow_up'
  if (posting.account.startsWith('Assets')) return 'f7:creditcard'
  if (posting.account.startsWith('Liabilities')) return 'f7:creditcard_fill'
  return 'f7:doc_text'
}

function getPostingIconClass(posting: Posting): string {
  if (posting.account.startsWith('Income')) return 'income-posting'
  if (posting.account.startsWith('Expenses')) return 'expense-posting'
  if (posting.account.startsWith('Assets')) return 'asset-posting'
  if (posting.account.startsWith('Liabilities')) return 'liability-posting'
  return ''
}

function getPostingAmountClass(posting: Posting): string {
  const amount = Number(posting.amount)
  if (amount > 0) return 'positive'
  if (amount < 0) return 'negative'
  return ''
}

function formatPostingAmount(posting: Posting): string {
  const amount = Number(posting.amount)
  const currency = posting.currency || 'CNY'
  const symbol = getCurrencySymbol(currency)
  const sign = amount >= 0 ? '+' : ''
  
  return `${sign}${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function confirmDelete() {
  f7.dialog.confirm(
    '确定要删除这笔交易吗？此操作无法撤销。',
    '删除交易',
    async () => {
      try {
        await transactionsApi.deleteTransaction(transaction.value!.id)
        // 标记交易列表需要刷新
        uiStore.markTransactionsNeedsRefresh()
        f7.toast.show({
          text: '交易已删除',
          closeTimeout: 2000
        })
        router.back()
      } catch (e: any) {
        f7.toast.show({
          text: e.message || '删除失败',
          closeTimeout: 2000
        })
      }
    }
  )
}

onMounted(() => {
  loadTransaction()
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

/* 错误状态 */
.error-state {
  text-align: center;
  padding: 60px 20px;
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-text {
  font-size: 16px;
  color: var(--f7-text-color);
  margin-bottom: 24px;
}

.retry-btn {
  display: inline-block;
}

/* 详情内容 */
.detail-content {
  padding-bottom: 80px;
}

/* 金额卡片 */
.amount-card {
  margin: 16px;
  padding: 24px;
  border-radius: 16px;
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
}

.amount-card.income-card {
  background: linear-gradient(135deg, #34c759 0%, #30d158 100%);
  box-shadow: 0 8px 32px rgba(52, 199, 89, 0.3);
}

.amount-card.expense-card {
  background: linear-gradient(135deg, #ff3b30 0%, #ff453a 100%);
  box-shadow: 0 8px 32px rgba(255, 59, 48, 0.3);
}

.amount-card.transfer-card {
  background: linear-gradient(135deg, #007aff 0%, #0a84ff 100%);
  box-shadow: 0 8px 32px rgba(0, 122, 255, 0.3);
}

.type-icon {
  margin-bottom: 12px;
  opacity: 0.9;
}

.amount-display {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -1px;
  margin-bottom: 8px;
}

.type-label {
  font-size: 14px;
  opacity: 0.85;
  font-weight: 500;
}

/* 区域标题 */
.section-header {
  font-size: 13px;
  color: #8e8e93;
  font-weight: 600;
  text-transform: uppercase;
  padding: 24px 16px 8px;
  margin-left: 16px;
}

/* 列表样式 */
.info-list,
.postings-list,
.meta-list {
  margin-top: 0;
}

.description-text {
  max-width: 200px;
  text-align: right;
  white-space: normal;
  word-break: break-word;
}

.id-text {
  font-family: monospace;
  font-size: 12px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 标签 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.tag-chip {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

/* 分录图标 */
.posting-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.posting-icon.income-posting {
  background: rgba(52, 199, 89, 0.12);
  color: #34c759;
}

.posting-icon.expense-posting {
  background: rgba(255, 59, 48, 0.12);
  color: #ff3b30;
}

.posting-icon.asset-posting {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.posting-icon.liability-posting {
  background: rgba(175, 82, 222, 0.12);
  color: #af52de;
}

/* 分录金额 */
.posting-amount {
  font-size: 15px;
  font-weight: 600;
  font-family: -apple-system, BlinkMacSystemFont, monospace;
}

.posting-amount.positive {
  color: #34c759;
}

.posting-amount.negative {
  color: #ff3b30;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .amount-card {
    background: linear-gradient(135deg, #5856d6 0%, #5e5ce6 100%);
  }
  
  .amount-card.income-card {
    background: linear-gradient(135deg, #30d158 0%, #28cd41 100%);
  }
  
  .amount-card.expense-card {
    background: linear-gradient(135deg, #ff453a 0%, #ff3b30 100%);
  }
  
  .amount-card.transfer-card {
    background: linear-gradient(135deg, #0a84ff 0%, #007aff 100%);
  }
  
  .tag-chip {
    background: rgba(10, 132, 255, 0.18);
    color: #0a84ff;
  }
  
  .posting-icon.income-posting {
    background: rgba(48, 209, 88, 0.18);
    color: #30d158;
  }
  
  .posting-icon.expense-posting {
    background: rgba(255, 69, 58, 0.18);
    color: #ff453a;
  }
  
  .posting-icon.asset-posting {
    background: rgba(10, 132, 255, 0.18);
    color: #0a84ff;
  }
  
  .posting-icon.liability-posting {
    background: rgba(191, 90, 242, 0.18);
    color: #bf5af2;
  }
  
  .posting-amount.positive {
    color: #30d158;
  }
  
  .posting-amount.negative {
    color: #ff453a;
  }
}
</style>
