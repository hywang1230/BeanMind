<template>
  <f7-page name="edit-transaction">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>编辑交易</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="handleSubmit" :class="{ disabled: loading }" :style="{ opacity: (!isFormValid || loading) ? 0.5 : 1 }">{{ loading ? '保存中' : (isMultiSelect ? '下一步' : '保存') }}</f7-link>
      </f7-nav-right>
    </f7-navbar>

    <!-- 加载状态 -->
    <div v-if="pageLoading" class="loading-container">
      <f7-preloader></f7-preloader>
    </div>

    <template v-else>
      <f7-block class="no-padding-vertical margin-vertical">
        <f7-segmented strong tag="div">
          <f7-button :active="formData.type === 'expense'" @click="selectType('expense')">支出</f7-button>
          <f7-button :active="formData.type === 'income'" @click="selectType('income')">收入</f7-button>
          <f7-button :active="formData.type === 'transfer'" @click="selectType('transfer')">转账</f7-button>
        </f7-segmented>
      </f7-block>

      <f7-list strong-ios dividers-ios inset-ios form>
        <!-- 账户/转出账户 -->
        <f7-list-item
          class="account-item"
          link="#"
          :title="formData.type === 'transfer' ? '转出账户' : '账户'"
          :after="formatAccountDisplay(formData.fromAccount) || '请选择'"
          @click="openFromAccountPicker"
        >
          <template #media>
            <i class="icon f7-icons">creditcard_fill</i>
          </template>
        </f7-list-item>

        <!-- 币种 -->
        <f7-list-item
          title="币种"
          :after="formData.currency"
          :link="availableCurrencies.length > 1 ? '#' : undefined"
          class="currency-trigger"
          @click="openCurrencyPopover"
        >
          <template #media>
            <i class="icon f7-icons">money_dollar_circle_fill</i>
          </template>
        </f7-list-item>

        <!-- 金额 -->
        <f7-list-item class="amount-item" title="金额">
          <template #media>
            <i class="icon f7-icons">money_yen_circle_fill</i>
          </template>
          <div class="amount-row">
            <AmountInput
              v-model="formData.amount"
              :allow-negative="formData.type !== 'transfer'"
              :currency="formData.currency"
            />
          </div>
        </f7-list-item>

        <!-- 分类 (非转账) -->
        <f7-list-item
          v-if="formData.type !== 'transfer'"
          class="account-item"
          link="#"
          title="分类"
          :after="formatAccountDisplay(formData.category) || '请选择'"
          @click="openCategoryPicker"
        >
          <template #media>
            <i class="icon f7-icons">folder_fill</i>
          </template>
        </f7-list-item>

        <!-- 转入账户 -->
        <f7-list-item
          v-if="formData.type === 'transfer'"
          class="account-item"
          link="#"
          title="转入账户"
          :after="formatAccountDisplay(formData.toAccount) || '请选择'"
          @click="openToAccountPicker"
        >
          <template #media>
            <i class="icon f7-icons">arrow_right_circle_fill</i>
          </template>
        </f7-list-item>

        <!-- 日期 -->
        <f7-list-item
          title="日期"
          :after="formData.date"
          link="#"
          @click="openCalendar"
        >
          <template #media>
            <i class="icon f7-icons">calendar_today</i>
          </template>
        </f7-list-item>

        <!-- 交易方 -->
        <f7-list-item
          title="交易方"
          :after="formData.payee || '请选择'"
          link="#"
          @click="openPayeePicker"
        >
          <template #media>
            <i class="icon f7-icons">person_2_fill</i>
          </template>
        </f7-list-item>

        <!-- 备注 -->
        <f7-list-input
          label="备注"
          type="textarea"
          v-model:value="formData.description"
          placeholder="添加备注"
          resizable
        >
          <template #media>
            <i class="icon f7-icons">pencil_circle</i>
          </template>
        </f7-list-input>

        <!-- 标签 -->
        <f7-list-input
          label="标签"
          type="text"
          v-model:value="formData.tagString"
          placeholder="标签用空格分隔"
          info="例如: 旅行 餐饮"
        >
          <template #media>
            <i class="icon f7-icons">tag_fill</i>
          </template>
        </f7-list-input>
      </f7-list>

      <f7-block v-if="error" class="text-color-red text-align-center">
        {{ error }}
      </f7-block>

      <!-- Pickers -->
      <AccountSelectionPopup
        v-model:opened="showCategoryPicker"
        title="选择分类"
        :root-types="categoryRoots"
        @select="onCategorySelect"
      />

      <PayeeSelectionPopup
        v-model:opened="showPayeePicker"
        @select="onPayeeSelect"
      />

      <AccountSelectionPopup
        v-model:opened="showFromAccountPicker"
        :title="formData.type === 'transfer' ? '选择转出账户' : '选择账户'"
        :root-types="accountRoots"
        @select="onFromAccountSelect"
      />

      <AccountSelectionPopup
        v-model:opened="showToAccountPicker"
        title="选择转入账户"
        :root-types="['Assets', 'Liabilities']"
        @select="onToAccountSelect"
      />

      <!-- Currency Popover -->
      <f7-popover
        class="currency-popover"
        :opened="showCurrencyPopover"
        @popover:closed="showCurrencyPopover = false"
        target-el=".currency-trigger"
      >
        <f7-list>
          <f7-list-item
            v-for="curr in availableCurrencies"
            :key="curr"
            :title="curr"
            link="#"
            popover-close
            @click="onCurrencySelect(curr)"
          >
            <template #media>
               <f7-icon v-if="formData.currency === curr" f7="checkmark_alt" size="20" color="blue"></f7-icon>
               <span v-else style="width: 20px; display: inline-block;"></span>
            </template>
          </f7-list-item>
        </f7-list>
      </f7-popover>
    </template>

  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { f7 } from 'framework7-vue'
import { useRouter, useRoute } from 'vue-router'
import { useTransactionStore, type TransactionDraft } from '../../stores/transaction'
import { useUIStore } from '../../stores/ui'
import { transactionsApi, type CreateTransactionRequest, type Posting, type Transaction } from '../../api/transactions'
import { accountsApi, type Account } from '../../api/accounts'
import AccountSelectionPopup from '../../components/AccountSelectionPopup.vue'
import PayeeSelectionPopup from '../../components/PayeeSelectionPopup.vue'
import AmountInput from '../../components/AmountInput.vue'

const router = useRouter()
const route = useRoute()
const transactionStore = useTransactionStore()
const uiStore = useUIStore()

// State
const pageLoading = ref(true)
const loading = ref(false)
const error = ref('')
const showCategoryPicker = ref(false)
const showPayeePicker = ref(false)
const showFromAccountPicker = ref(false)
const showToAccountPicker = ref(false)
const allAccounts = ref<Account[]>([])
const originalTransaction = ref<Transaction | null>(null)

// 保存原始的分配信息
const originalCategoryDistributions = ref<Record<string, number>>({})
const originalAccountDistributions = ref<Record<string, number>>({})

interface TransactionFormData {
  type: 'expense' | 'income' | 'transfer'
  amount: number | undefined
  currency: string
  category: string[]
  fromAccount: string[]
  toAccount: string[]
  date: string
  payee: string
  description: string
  tagString: string
}

const formData = ref<TransactionFormData>({
  type: 'expense',
  amount: undefined,
  currency: 'CNY',
  category: [],
  fromAccount: [],
  toAccount: [],
  date: new Date().toISOString().split('T')[0] ?? '',
  payee: '',
  description: '',
  tagString: ''
})

// 从交易数据解析表单数据
function parseTransactionToForm(transaction: Transaction) {
  // 解析交易类型
  const txnType = transaction.transaction_type || determineTransactionType(transaction)
  formData.value.type = txnType as 'expense' | 'income' | 'transfer'
  
  // 解析日期
  formData.value.date = transaction.date
  
  // 解析交易方
  formData.value.payee = transaction.payee || ''
  
  // 解析描述
  formData.value.description = transaction.description || ''
  
  // 解析标签
  formData.value.tagString = (transaction.tags || []).join(' ')
  
  // 解析 postings
  const categories: string[] = []
  const fromAccounts: string[] = []
  const toAccounts: string[] = []
  let totalAmount = 0
  let currency = 'CNY'
  
  // 清空原始分配
  originalCategoryDistributions.value = {}
  originalAccountDistributions.value = {}
  
  for (const posting of transaction.postings) {
    const amount = parseFloat(posting.amount)
    currency = posting.currency || 'CNY'
    
    if (txnType === 'expense') {
      // 支出类：
      // - Expenses 账户金额为正（或负，退款），直接作为分类金额（保持符号）
      // - Assets/Liabilities 账户金额为负（或正，退款），需要取反以匹配 "支出金额" 的概念（Total Amount）
      //   例如：消费 100。Total 100。Liab -100。Store -> 100。
      //   例如：退款 -6。Total -6。Liab +6。Store -> -6。
      if (posting.account.startsWith('Expenses:')) {
        categories.push(posting.account)
        originalCategoryDistributions.value[posting.account] = amount
        totalAmount += amount
      } else if (posting.account.startsWith('Assets:') || posting.account.startsWith('Liabilities:')) {
        fromAccounts.push(posting.account)
        originalAccountDistributions.value[posting.account] = -amount
      }
    } else if (txnType === 'income') {
      // 收入类：
      // - Income 账户金额通常为负。Total Amount 为正。
      //   例如：收入 100。Total 100。Income -100。Store -> 100 (-(-100))。
      // - Assets 账户金额为正。Total 100。Asset 100。Store -> 100。
      if (posting.account.startsWith('Income:')) {
        categories.push(posting.account)
        originalCategoryDistributions.value[posting.account] = -amount
        totalAmount += -amount
      } else if (posting.account.startsWith('Assets:') || posting.account.startsWith('Liabilities:')) {
        fromAccounts.push(posting.account)
        originalAccountDistributions.value[posting.account] = amount
      }
    } else if (txnType === 'transfer') {
      // 转账：
      // From: negative. Store -> positive (abs).
      // To: positive. Store -> positive (abs).
      // Total Amount is positive.
      if (amount < 0) {
        fromAccounts.push(posting.account)
        originalAccountDistributions.value[posting.account] = Math.abs(amount)
        totalAmount += Math.abs(amount)
      } else {
        toAccounts.push(posting.account)
        originalAccountDistributions.value[posting.account] = Math.abs(amount)
      }
    }
  }
  
  formData.value.category = categories
  formData.value.fromAccount = fromAccounts
  formData.value.toAccount = toAccounts
  
  // 表单中的金额始终为正数，符号由 buildPostings 根据交易类型决定
  formData.value.amount = totalAmount
  
  formData.value.currency = currency
}

// 确定交易类型
function determineTransactionType(transaction: Transaction): string {
  const hasExpense = transaction.postings.some(p => p.account.startsWith('Expenses:'))
  const hasIncome = transaction.postings.some(p => p.account.startsWith('Income:'))
  
  if (hasExpense) return 'expense'
  if (hasIncome) return 'income'
  return 'transfer'
}

// Lifecycle
onMounted(async () => {
  const transactionId = route.params.id as string
  
  if (!transactionId) {
    error.value = '无效的交易ID'
    pageLoading.value = false
    return
  }
  
  try {
    // 加载账户信息
    const res = await accountsApi.getAccounts()
    if (Array.isArray(res)) {
      allAccounts.value = res
    } else if (res && (res as any).accounts) {
      allAccounts.value = (res as any).accounts
    }
    
    // 加载交易详情
    const transaction = await transactionsApi.getTransaction(transactionId)
    originalTransaction.value = transaction
    
    // 解析交易数据到表单
    parseTransactionToForm(transaction)
    
  } catch (err: any) {
    console.error('Failed to load transaction:', err)
    error.value = err.message || '加载交易失败'
  } finally {
    pageLoading.value = false
  }
})

// Helpers
function getSelectedAccountsInfo(names: string[]) {
  return allAccounts.value.filter(acc => names.includes(acc.name))
}

const DEFAULT_CURRENCIES = ['CNY', 'USD', 'HKD']

// Currency Logic
const availableCurrencies = computed(() => {
  const selectedNames = [
    ...formData.value.fromAccount,
    ...formData.value.toAccount,
    ...formData.value.category
  ]
  if (selectedNames.length === 0) return DEFAULT_CURRENCIES
  
  const accountsInfo = getSelectedAccountsInfo(selectedNames)
  if (accountsInfo.length === 0) return DEFAULT_CURRENCIES
  
  // Intersection of currencies
  let common: string[] | null = null

  for (const acc of accountsInfo) {
    const accCurrs = (acc.currencies && acc.currencies.length > 0) ? acc.currencies : DEFAULT_CURRENCIES
    if (common === null) {
      common = [...accCurrs]
    } else {
      common = common.filter(c => accCurrs.includes(c))
    }
  }
  
  return common || []
})

watch(availableCurrencies, (newVal) => {
  if (newVal && newVal.length > 0) {
    if (!newVal.includes(formData.value.currency)) {
      if (newVal.includes('CNY')) {
        formData.value.currency = 'CNY'
      } else {
        formData.value.currency = newVal[0] || 'CNY'
      }
    }
  }
}, { immediate: true })

// Computed Props for Picker Roots
const categoryRoots = computed(() => {
  return formData.value.type === 'expense' ? ['Expenses'] : ['Income']
})

const accountRoots = computed(() => {
  return ['Assets', 'Liabilities']
})

const isFormValid = computed(() => {
  if (formData.value.amount === undefined || formData.value.amount === 0) return false
  if (formData.value.type === 'transfer' && formData.value.amount < 0) return false
  if (!formData.value.date) return false
  if (formData.value.fromAccount.length === 0) return false
  
  if (formData.value.type === 'transfer') {
    return formData.value.toAccount.length > 0
  } else {
    return formData.value.category.length > 0
  }
})

// Navigation
function goBack() {
  transactionStore.clearTransactionDraft()
  router.back()
}

// Types
function selectType(type: 'expense' | 'income' | 'transfer') {
  formData.value.type = type
  if (type === 'transfer') {
      formData.value.category = []
  } else if (type === 'expense' && formData.value.category.some(c => c.startsWith('Income'))) {
      formData.value.category = []
  } else if (type === 'income' && formData.value.category.some(c => c.startsWith('Expenses'))) {
      formData.value.category = []
  }
}

// Picker Handlers
function openCategoryPicker() { showCategoryPicker.value = true }
function openPayeePicker() { showPayeePicker.value = true }
function openFromAccountPicker() { showFromAccountPicker.value = true }
function openToAccountPicker() { showToAccountPicker.value = true }

function onCategorySelect(val: string[]) { formData.value.category = val }
function onPayeeSelect(val: string) { formData.value.payee = val }
function onFromAccountSelect(val: string[]) { formData.value.fromAccount = val }
function onToAccountSelect(val: string[]) { formData.value.toAccount = val }

function formatAccountDisplay(names: string | string[]): string {
  if (!names) return ''
  if (Array.isArray(names)) {
    return names.join(', ')
  }
  return names
}

// Calendar Logic
let calendarInstance: any = null

function openCalendar() {
  const currentDateStr = formData.value.date || new Date().toISOString().split('T')[0] || ''
  const parts = currentDateStr.split('-').map(Number)
  const y = parts[0] || new Date().getFullYear()
  const m = parts[1] || (new Date().getMonth() + 1)
  const d = parts[2] || new Date().getDate()
  const currentDate = new Date(y, m - 1, d)

  if (!calendarInstance) {
    calendarInstance = f7.calendar.create({
      closeOnSelect: true,
      value: [currentDate],
      on: {
        change: function (_calendar: any, values: unknown) {
          const dateValues = values as Date[]
          if (dateValues && dateValues[0]) {
            const d = dateValues[0]
            const year = d.getFullYear()
            const month = String(d.getMonth() + 1).padStart(2, '0')
            const day = String(d.getDate()).padStart(2, '0')
            formData.value.date = `${year}-${month}-${day}`
          }
        }
      }
    })
  } else {
    calendarInstance.setValue([currentDate])
  }
  calendarInstance.open()
}

onBeforeUnmount(() => {
  if (calendarInstance) {
    calendarInstance.destroy()
    calendarInstance = null
  }
})

// Submission Logic
const showCurrencyPopover = ref(false)

function openCurrencyPopover() {
  if (availableCurrencies.value.length > 1) {
    showCurrencyPopover.value = true
  }
}

function onCurrencySelect(curr: string) {
  formData.value.currency = curr
  showCurrencyPopover.value = false
}

function buildPostings(): Posting[] {
  const posts: Posting[] = []
  const amt = formData.value.amount || 0
  const currency = formData.value.currency

  const fromCount = formData.value.fromAccount.length
  const toCount = formData.value.toAccount.length
  const catCount = formData.value.category.length

  if (formData.value.type === 'expense') {
    // Expense: +Expense, -Asset
    formData.value.category.forEach(cat => {
      posts.push({ account: cat, amount: (amt / catCount).toFixed(2), currency })
    })
    formData.value.fromAccount.forEach(acc => {
      posts.push({ account: acc, amount: (-amt / fromCount).toFixed(2), currency })
    })
  } else if (formData.value.type === 'income') {
    // Income: +Asset, -Income
    formData.value.fromAccount.forEach(acc => {
      posts.push({ account: acc, amount: (amt / fromCount).toFixed(2), currency })
    })
    formData.value.category.forEach(cat => {
      posts.push({ account: cat, amount: (-amt / catCount).toFixed(2), currency })
    })
  } else if (formData.value.type === 'transfer') {
    // Transfer: -From, +To
    formData.value.fromAccount.forEach(acc => {
      posts.push({ account: acc, amount: (-amt / fromCount).toFixed(2), currency })
    })
    formData.value.toAccount.forEach(acc => {
      posts.push({ account: acc, amount: (amt / toCount).toFixed(2), currency })
    })
  }
  return posts
}

const isMultiSelect = computed(() => {
  if (formData.value.type === 'transfer') {
      return formData.value.fromAccount.length > 1 || formData.value.toAccount.length > 1
  }
  return formData.value.category.length > 1 || formData.value.fromAccount.length > 1
})

async function handleSubmit() {
  if (!isFormValid.value) {
      f7.toast.show({ text: '请填写所有必填项', position: 'center', closeTimeout: 2000 })
      return 
  }

  if (isMultiSelect.value) {
      // Create draft with edit mode info
      const draft: TransactionDraft = {
          ...formData.value,
          amount: formData.value.amount || 0,
          // 使用原始分配信息作为初始值
          categoryDistributions: { ...originalCategoryDistributions.value },
          accountDistributions: { ...originalAccountDistributions.value }
      }
      transactionStore.setTransactionDraft(draft)
      
      // 保存编辑模式信息到 sessionStorage
      sessionStorage.setItem('editTransactionId', originalTransaction.value?.id || '')

      // Navigate
      if (formData.value.type !== 'transfer' && formData.value.category.length > 1) {
           router.push({ path: '/transactions/distribute', query: { type: 'category', mode: 'edit', depth: 2 } })
      } else if (formData.value.type === 'transfer') {
           if (formData.value.fromAccount.length > 1) {
                router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'from', mode: 'edit', depth: 2 } })
           } else {
                router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'to', mode: 'edit', depth: 2 } })
           }
      } else {
           // Expense/Income with multiple accounts
           router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'from', mode: 'edit', depth: 2 } })
      }
      return
  }

  loading.value = true
  error.value = ''

  try {
      const tags = formData.value.tagString
        .split(' ')
        .map(t => t.trim())
        .filter(t => t.length > 0)

      const request: CreateTransactionRequest = {
          date: formData.value.date,
          description: formData.value.description || undefined,
          payee: formData.value.payee || undefined,
          postings: buildPostings(),
          tags: tags.length > 0 ? tags : undefined
      }

      await transactionStore.updateTransaction(originalTransaction.value!.id, request)
      // 标记交易列表需要刷新
      uiStore.markTransactionsNeedsRefresh()
      
      f7.toast.show({ text: '交易已更新', position: 'center', closeTimeout: 2000 })
      router.back()
  } catch (err: any) {
      console.error(err)
      error.value = err.message || '保存失败'
  } finally {
      loading.value = false
  }
}
</script>

<style scoped>
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

.margin-vertical {
    margin-top: 16px;
    margin-bottom: 16px;
}

.amount-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.currency-badge, .currency-badge-fixed {
  background: var(--f7-theme-color);
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  font-weight: bold;
}

.currency-badge-fixed {
  background: var(--f7-list-item-after-text-color, #8e8e93);
}

/* 账户名称显示优化：保持标题不被隐藏，账户名从左侧截断 */
.account-item :deep(.item-after) {
  max-width: 70%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  direction: rtl;
  text-align: left;
}

.account-item :deep(.item-title) {
  flex-shrink: 0;
}
</style>
