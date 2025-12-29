<template>
  <f7-page name="account-detail">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>账户详情</f7-nav-title>
    </f7-navbar>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <f7-preloader></f7-preloader>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
      <f7-button fill round @click="loadAccountDetail" class="retry-btn">
        重试
      </f7-button>
    </div>

    <!-- 账户详情内容 -->
    <div v-else-if="account" class="detail-content">
      <!-- 账户卡片 -->
      <div class="account-card" :class="getAccountCardClass()">
        <div class="account-icon">
          <f7-icon :ios="getAccountIcon()" size="32"></f7-icon>
        </div>
        <div class="account-name-display">{{ getShortName(account.name) }}</div>
        <div class="account-full-name">{{ account.name }}</div>
        <div class="status-badge" :class="account.is_active ? 'active' : 'closed'">
          {{ account.is_active ? '活跃' : '已关闭' }}
        </div>
      </div>

      <!-- 基本信息 -->
      <f7-list strong-ios dividers-ios inset class="info-list">
        <f7-list-item title="账户类型" :after="getAccountTypeLabel(account.account_type)">
          <template #media>
            <i class="icon f7-icons">folder_fill</i>
          </template>
        </f7-list-item>

        <f7-list-item title="支持币种" :after="account.currencies.join(', ')">
          <template #media>
            <i class="icon f7-icons">money_dollar_circle_fill</i>
          </template>
        </f7-list-item>

        <f7-list-item v-if="account.open_date" title="开户日期" :after="formatDate(account.open_date)">
          <template #media>
            <i class="icon f7-icons">calendar</i>
          </template>
        </f7-list-item>

        <f7-list-item v-if="account.close_date" title="关闭日期" :after="formatDate(account.close_date)">
          <template #media>
            <i class="icon f7-icons">calendar_badge_minus</i>
          </template>
        </f7-list-item>
      </f7-list>

      <!-- 余额信息 -->
      <f7-block-title>账户余额</f7-block-title>
      <f7-list strong-ios dividers-ios inset class="balance-list">
        <f7-list-item v-if="loadingBalance" title="加载中...">
          <template #media>
            <f7-preloader :size="20"></f7-preloader>
          </template>
        </f7-list-item>

        <f7-list-item v-else-if="balances.length === 0" title="暂无余额数据">
          <template #media>
            <i class="icon f7-icons">info_circle</i>
          </template>
          <template #after>
            <f7-link @click="loadBalance">刷新</f7-link>
          </template>
        </f7-list-item>

        <f7-list-item v-else v-for="balance in balances" :key="balance.currency" :title="balance.currency">
          <template #media>
            <div class="balance-icon">
              <f7-icon ios="f7:money_dollar_circle" size="20"></f7-icon>
            </div>
          </template>
          <template #after>
            <span class="balance-amount" :class="getBalanceClass(balance.amount)">
              {{ formatAmount(balance.amount) }}
            </span>
          </template>
        </f7-list-item>

        <f7-list-item v-if="balances.length > 0">
          <template #title>
            <f7-link @click="loadBalance">刷新余额</f7-link>
          </template>
        </f7-list-item>
      </f7-list>

      <!-- 子账户 -->
      <template v-if="children.length > 0">
        <f7-block-title>子账户 ({{ children.length }})</f7-block-title>
        <f7-list strong-ios dividers-ios inset class="children-list">
          <f7-list-item v-for="child in children" :key="child.name" :title="getShortName(child.name)"
            :subtitle="child.currencies.join(', ')" link="#" @click="navigateToChild(child.name)">
            <template #media>
              <div class="child-icon" :class="getChildIconClass(child)">
                <f7-icon ios="f7:folder" size="18"></f7-icon>
              </div>
            </template>
          </f7-list-item>
        </f7-list>
      </template>

      <!-- 关闭账户按钮 -->
      <f7-block v-if="account.is_active">
        <f7-button large fill color="red" @click="showCloseModal = true">
          关闭账户
        </f7-button>
      </f7-block>

      <!-- 重新开启账户按钮 -->
      <f7-block v-if="!account.is_active">
        <f7-button large fill color="green" :disabled="reopeningAccount" @click="handleReopenAccount">
          {{ reopeningAccount ? '开启中...' : '重新开启账户' }}
        </f7-button>
      </f7-block>
    </div>

    <!-- 关闭账户模态框 -->
    <f7-popup :opened="showCloseModal" @popup:closed="showCloseModal = false">
      <f7-page>
        <f7-navbar title="关闭账户">
          <f7-nav-right>
            <f7-link popup-close>取消</f7-link>
          </f7-nav-right>
        </f7-navbar>

        <f7-block class="warning-block">
          <div class="warning-icon">⚠️</div>
          <div class="warning-text">
            <p><strong>确定要关闭此账户吗?</strong></p>
            <p>账户名称: {{ account?.name }}</p>
          </div>
        </f7-block>

        <f7-block v-if="hasBalance" class="error-block">
          <p>⚠️ 此账户还有余额,请先清空余额后再关闭</p>
        </f7-block>

        <f7-list v-if="!hasBalance" strong-ios dividers-ios inset>
          <f7-list-input label="关闭日期" type="date" :value="closeDate" @input="closeDate = $event.target.value"
            :max="today"></f7-list-input>
        </f7-list>

        <f7-block v-if="closeError" class="error-block">
          <p>{{ closeError }}</p>
        </f7-block>

        <f7-block>
          <f7-button large fill color="red" :disabled="closingAccount || hasBalance" @click="handleCloseAccount">
            {{ closingAccount ? '关闭中...' : '确认关闭' }}
          </f7-button>
        </f7-block>
      </f7-page>
    </f7-popup>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { accountsApi, type AccountDetail, type Balance, type Account } from '../../api/accounts'
import { f7 } from 'framework7-vue'

const router = useRouter()
const route = useRoute()

const accountName = computed(() => {
  const name = route.params.accountName
  if (Array.isArray(name)) {
    return name[0] || ''
  }
  return name || ''
})

const loading = ref(false)
const error = ref('')
const account = ref<AccountDetail | null>(null)

const balances = ref<Balance[]>([])
const loadingBalance = ref(false)

const children = ref<Account[]>([])

const showCloseModal = ref(false)
const closeDate = ref(new Date().toISOString().split('T')[0])
const closingAccount = ref(false)
const closeError = ref('')
const reopeningAccount = ref(false)

const today = new Date().toISOString().split('T')[0]

const accountTypes: Record<string, string> = {
  'Assets': '资产',
  'Liabilities': '负债',
  'Equity': '权益',
  'Income': '收入',
  'Expenses': '支出'
}

const hasBalance = computed(() => {
  if (!balances.value || !Array.isArray(balances.value)) return false
  return balances.value.some(b => Math.abs(b.amount) > 0.01)
})

function getAccountTypeLabel(type: string): string {
  return accountTypes[type] || type
}

function getShortName(fullName: string): string {
  const parts = fullName.split(':')
  return parts[parts.length - 1] ?? ''
}

function formatAmount(amount: number | undefined | null): string {
  if (amount === undefined || amount === null) return '0.00'
  return amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return ''
  // 处理 ISO 格式日期，取 yyyy-MM-dd 部分
  return dateStr.split('T')[0] ?? dateStr
}

function getBalanceClass(amount: number): string {
  if (amount > 0) return 'positive'
  if (amount < 0) return 'negative'
  return ''
}

function getAccountCardClass(): string {
  if (!account.value) return ''
  const type = account.value.account_type
  if (type === 'Assets') return 'assets-card'
  if (type === 'Liabilities') return 'liabilities-card'
  if (type === 'Income') return 'income-card'
  if (type === 'Expenses') return 'expenses-card'
  if (type === 'Equity') return 'equity-card'
  return ''
}

function getAccountIcon(): string {
  if (!account.value) return 'f7:folder_fill'
  const type = account.value.account_type
  if (type === 'Assets') return 'f7:creditcard_fill'
  if (type === 'Liabilities') return 'f7:doc_text_fill'
  if (type === 'Income') return 'f7:arrow_down_circle_fill'
  if (type === 'Expenses') return 'f7:arrow_up_circle_fill'
  if (type === 'Equity') return 'f7:chart_pie_fill'
  return 'f7:folder_fill'
}

function getChildIconClass(child: Account): string {
  const type = child.account_type
  if (type === 'Assets') return 'assets-icon'
  if (type === 'Liabilities') return 'liabilities-icon'
  if (type === 'Income') return 'income-icon'
  if (type === 'Expenses') return 'expenses-icon'
  if (type === 'Equity') return 'equity-icon'
  return ''
}

async function loadAccountDetail() {
  loading.value = true
  error.value = ''

  try {
    account.value = await accountsApi.getAccountDetail(accountName.value)

    // 同时加载余额和子账户
    await Promise.all([
      loadBalance(),
      loadChildren()
    ])
  } catch (err: any) {
    console.error('Failed to load account detail:', err)
    error.value = err.message || '加载账户详情失败'
  } finally {
    loading.value = false
  }
}

async function loadBalance() {
  loadingBalance.value = true
  try {
    balances.value = await accountsApi.getBalance(accountName.value)
  } catch (err) {
    console.error('Failed to load balance:', err)
  } finally {
    loadingBalance.value = false
  }
}

async function loadChildren() {
  try {
    children.value = await accountsApi.getChildren(accountName.value)
  } catch (err) {
    console.error('Failed to load children:', err)
  }
}

async function handleCloseAccount() {
  if (hasBalance.value) {
    closeError.value = '账户还有余额,无法关闭'
    return
  }

  closingAccount.value = true
  closeError.value = ''

  try {
    await accountsApi.closeAccount(accountName.value, {
      close_date: closeDate.value
    })

    f7.toast.create({
      text: '账户已成功关闭',
      position: 'center',
      closeTimeout: 2000
    }).open()

    showCloseModal.value = false

    // 重新加载账户详情
    await loadAccountDetail()
  } catch (err: any) {
    console.error('Failed to close account:', err)
    closeError.value = err.message || '关闭账户失败'
  } finally {
    closingAccount.value = false
  }
}

function navigateToChild(childName: string) {
  router.push(`/accounts/${encodeURIComponent(childName)}`)
}

function goBack() {
  router.back()
}

async function handleReopenAccount() {
  reopeningAccount.value = true

  try {
    await accountsApi.reopenAccount(accountName.value)

    f7.toast.create({
      text: '账户已成功重新开启',
      position: 'center',
      closeTimeout: 2000
    }).open()

    // 重新加载账户详情
    await loadAccountDetail()
  } catch (err: any) {
    console.error('Failed to reopen account:', err)
    f7.toast.create({
      text: err.message || '重新开启账户失败',
      position: 'center',
      closeTimeout: 2000,
      cssClass: 'error-toast'
    }).open()
  } finally {
    reopeningAccount.value = false
  }
}

onMounted(() => {
  loadAccountDetail()
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

/* 账户卡片 */
.account-card {
  margin: 16px;
  padding: 24px;
  border-radius: 16px;
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
}

.account-card.assets-card {
  background: linear-gradient(135deg, #007aff 0%, #0a84ff 100%);
  box-shadow: 0 8px 32px rgba(0, 122, 255, 0.3);
}

.account-card.liabilities-card {
  background: linear-gradient(135deg, #af52de 0%, #bf5af2 100%);
  box-shadow: 0 8px 32px rgba(175, 82, 222, 0.3);
}

.account-card.income-card {
  background: linear-gradient(135deg, #34c759 0%, #30d158 100%);
  box-shadow: 0 8px 32px rgba(52, 199, 89, 0.3);
}

.account-card.expenses-card {
  background: linear-gradient(135deg, #ff3b30 0%, #ff453a 100%);
  box-shadow: 0 8px 32px rgba(255, 59, 48, 0.3);
}

.account-card.equity-card {
  background: linear-gradient(135deg, #ff9500 0%, #ff9f0a 100%);
  box-shadow: 0 8px 32px rgba(255, 149, 0, 0.3);
}

.account-icon {
  margin-bottom: 12px;
  opacity: 0.9;
}

.account-name-display {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -1px;
  margin-bottom: 8px;
}

.account-full-name {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 12px;
}

.status-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
}

.status-badge.active {
  background: rgba(52, 199, 89, 0.3);
}

.status-badge.closed {
  background: rgba(255, 59, 48, 0.3);
}

/* 列表样式 */
.info-list,
.balance-list,
.children-list {
  margin-top: 0;
}

/* 余额图标 */
.balance-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

/* 余额金额 */
.balance-amount {
  font-size: 16px;
  font-weight: 600;
  font-family: -apple-system, BlinkMacSystemFont, monospace;
}

.balance-amount.positive {
  color: #34c759;
}

.balance-amount.negative {
  color: #ff3b30;
}

/* 子账户图标 */
.child-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.child-icon.assets-icon {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.child-icon.liabilities-icon {
  background: rgba(175, 82, 222, 0.12);
  color: #af52de;
}

.child-icon.income-icon {
  background: rgba(52, 199, 89, 0.12);
  color: #34c759;
}

.child-icon.expenses-icon {
  background: rgba(255, 59, 48, 0.12);
  color: #ff3b30;
}

.child-icon.equity-icon {
  background: rgba(255, 149, 0, 0.12);
  color: #ff9500;
}

/* 警告块 */
.warning-block {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #fff3cd;
  border-radius: 8px;
  margin: 16px;
}

.warning-icon {
  font-size: 24px;
}

.warning-text {
  flex: 1;
}

.warning-text p {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #333;
}

.warning-text p:last-child {
  margin-bottom: 0;
}

/* 错误块 */
.error-block {
  background: #fee;
  color: #c33;
  padding: 16px;
  border-radius: 8px;
  margin: 16px;
}

.error-block p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .account-card.assets-card {
    background: linear-gradient(135deg, #0a84ff 0%, #007aff 100%);
  }

  .account-card.liabilities-card {
    background: linear-gradient(135deg, #bf5af2 0%, #af52de 100%);
  }

  .account-card.income-card {
    background: linear-gradient(135deg, #30d158 0%, #28cd41 100%);
  }

  .account-card.expenses-card {
    background: linear-gradient(135deg, #ff453a 0%, #ff3b30 100%);
  }

  .account-card.equity-card {
    background: linear-gradient(135deg, #ff9f0a 0%, #ff9500 100%);
  }

  .balance-icon {
    background: rgba(10, 132, 255, 0.18);
    color: #0a84ff;
  }

  .balance-amount.positive {
    color: #30d158;
  }

  .balance-amount.negative {
    color: #ff453a;
  }

  .child-icon.assets-icon {
    background: rgba(10, 132, 255, 0.18);
    color: #0a84ff;
  }

  .child-icon.liabilities-icon {
    background: rgba(191, 90, 242, 0.18);
    color: #bf5af2;
  }

  .child-icon.income-icon {
    background: rgba(48, 209, 88, 0.18);
    color: #30d158;
  }

  .child-icon.expenses-icon {
    background: rgba(255, 69, 58, 0.18);
    color: #ff453a;
  }

  .child-icon.equity-icon {
    background: rgba(255, 159, 10, 0.18);
    color: #ff9f0a;
  }

  .warning-block {
    background: rgba(255, 204, 0, 0.2);
  }

  .warning-text p {
    color: var(--f7-text-color);
  }

  .error-block {
    background: rgba(255, 69, 58, 0.2);
    color: #ff453a;
  }
}
</style>
